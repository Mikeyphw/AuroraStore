/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import java.io.File
import java.io.RandomAccessFile

/**
 * A deliberately narrow, bounded ZIP central-directory preflight BEFORE ZipFile
 * creates its own entry index. No extraction or source attribution occurs here.
 * ZIP64, multivolume, self-extracting, encrypted and non-ASCII-name archives are
 * refused until independently audited. Only normal STORED/DEFLATED ZIPs qualify.
 */
internal object ArtifactZipPreflight {
    data class Entry(
        val name: String,
        val directory: Boolean,
        val size: Long,
        val compressed: Long,
        val crc: Long,
        val method: Int
    )

    private fun fail(why: String): Nothing = throw IllegalArgumentException("Unsafe ZIP: $why")
    private fun RandomAccessFile.u16(): Int = readUnsignedByte() or (readUnsignedByte() shl 8)
    private fun RandomAccessFile.u32(): Long = u16().toLong() or (u16().toLong() shl 16)

    private fun checkExtraFields(zip: RandomAccessFile, byteCount: Int, end: Long) {
        val start = zip.filePointer
        val finish = checkedAdd(start, byteCount.toLong(), end, "ZIP extra field extent")
        while (zip.filePointer < finish) {
            if (finish - zip.filePointer < 4L) fail("truncated ZIP extra-field header")
            val id = zip.u16()
            val size = zip.u16()
            if (id == 0x0001) fail("ZIP64 extra field is unsupported")
            zip.seek(checkedAdd(zip.filePointer, size.toLong(), finish, "ZIP extra field"))
        }
        if (zip.filePointer != finish) fail("ZIP extra field length mismatch")
    }

    private fun checkedAdd(a: Long, b: Long, max: Long, label: String): Long {
        if (a < 0 || b < 0 || a > max || b > max - a) fail("invalid $label")
        return a + b
    }

    fun inspect(file: File): List<Entry> = RandomAccessFile(file, "r").use { zip ->
        val length = zip.length()
        if (length < 22 || length > ArtifactArchivePolicy.MAX_SOURCE_BYTES) fail("source size")

        // The EOCD is confined to the last 22 + 65535 bytes by the ZIP format.
        // Never feed an unbounded central directory to java.util.zip.ZipFile.
        val tailLength = minOf(length, 22L + 65535L).toInt()
        val tail = ByteArray(tailLength)
        zip.seek(length - tailLength)
        zip.readFully(tail)
        fun tail16(i: Int) = (tail[i].toInt() and 255) or ((tail[i + 1].toInt() and 255) shl 8)
        var endAt = -1
        for (i in tailLength - 22 downTo 0) {
            if (tail[i] == 0x50.toByte() && tail[i + 1] == 0x4b.toByte() &&
                tail[i + 2] == 5.toByte() && tail[i + 3] == 6.toByte() &&
                i + 22 + tail16(i + 20) == tailLength
            ) {
                endAt = i
                break
            }
        }
        if (endAt < 0) fail("end of central directory missing or trailing data")
        val eocd = length - tailLength + endAt
        zip.seek(eocd + 4)
        val disk = zip.u16()
        val centralDisk = zip.u16()
        val diskEntries = zip.u16()
        val count = zip.u16()
        val directoryBytes = zip.u32()
        val directoryOffset = zip.u32()
        if (disk != 0 || centralDisk != 0 || diskEntries != count) fail("multivolume ZIP")
        if (count == 0 || count == 0xffff || count > ArtifactArchivePolicy.MAX_ITEMS ||
            directoryBytes == 0xffffffffL || directoryOffset == 0xffffffffL
        ) fail("unbounded or ZIP64 directory")
        if (directoryOffset == 0L) fail("missing local entry headers")
        if (checkedAdd(directoryOffset, directoryBytes, eocd, "central directory") != eocd) {
            fail("central directory extent or prepended payload")
        }

        zip.seek(directoryOffset)
        val result = ArrayList<Entry>(count)
        val usedNames = HashSet<String>(count)
        val occupied = ArrayList<Pair<Long, Long>>(count)
        var totalExpanded = 0L
        var apks = 0
        repeat(count) {
            if (zip.filePointer + 46 > eocd || zip.u32() != 0x02014b50L) fail("central entry header")
            val madeBy = zip.u16()
            zip.u16() // version needed
            val flags = zip.u16()
            val method = zip.u16()
            zip.skipBytes(4) // DOS time and date
            val crc = zip.u32()
            val compressed = zip.u32()
            val size = zip.u32()
            val nameLen = zip.u16()
            val extraLen = zip.u16()
            val commentLen = zip.u16()
            val startDisk = zip.u16()
            zip.u16() // internal attributes
            val external = zip.u32()
            val localOffset = zip.u32()
            if (flags and (0xffff xor 0x080e) != 0 || method !in listOf(0, 8) || startDisk != 0) {
                fail("encryption, unsupported flags/method or disk")
            }
            if (nameLen !in 1..240 || compressed == 0xffffffffL || size == 0xffffffffL ||
                localOffset == 0xffffffffL
            ) fail("ZIP64 or invalid entry lengths")
            val after = checkedAdd(zip.filePointer, nameLen + extraLen + commentLen.toLong(), eocd,
                "central entry extent")
            val nameBytes = ByteArray(nameLen)
            zip.readFully(nameBytes)
            // Fail closed on encoding ambiguities between central and local names.
            if (nameBytes.any { (it.toInt() and 255) !in 0x20..0x7e }) fail("non-ASCII entry name")
            val name = String(nameBytes, Charsets.US_ASCII)
            checkExtraFields(zip, extraLen, after)
            val isDirectory = name.endsWith('/')
            val safeName = name.removeSuffix("/")
            val kind = ArtifactArchivePolicy.classify(safeName, isDirectory)
                ?: fail("unsafe or unsupported entry name")
            if (!usedNames.add(safeName.lowercase(java.util.Locale.ROOT))) fail("duplicate path")
            val unixMode = if ((madeBy ushr 8) == 3) (external ushr 16).toInt() and 0xf000 else 0
            if (unixMode != 0 && unixMode != 0x8000 && unixMode != 0x4000) {
                fail("symbolic link or special file")
            }
            if (unixMode == 0x4000 && !isDirectory) fail("directory type mismatch")
            if (unixMode == 0x8000 && isDirectory) fail("file type mismatch")
            if (isDirectory && (size != 0L || kind != ArtifactArchivePolicy.Entry.DIRECTORY)) {
                fail("directory with content")
            }
            if (!isDirectory && !ArtifactArchivePolicy.safeSize(size, compressed,
                    kind == ArtifactArchivePolicy.Entry.APK)) fail("entry size or ratio")
            if (kind == ArtifactArchivePolicy.Entry.APK && ++apks > ArtifactArchivePolicy.MAX_APKS) {
                fail("too many APKs")
            }
            totalExpanded = checkedAdd(totalExpanded, size, ArtifactArchivePolicy.MAX_TOTAL_APK_BYTES,
                "total expanded data")
            zip.seek(after)
            val nextCentral = zip.filePointer

            if (localOffset >= directoryOffset || localOffset + 30L > directoryOffset) {
                fail("local header location")
            }
            zip.seek(localOffset)
            if (zip.u32() != 0x04034b50L) fail("local entry signature")
            zip.u16() // version needed
            val localFlags = zip.u16()
            val localMethod = zip.u16()
            zip.skipBytes(4)
            val localCrc = zip.u32()
            val localCompressed = zip.u32()
            val localSize = zip.u32()
            val localNameLen = zip.u16()
            val localExtraLen = zip.u16()
            if (localFlags != flags || localMethod != method || localNameLen != nameLen) {
                fail("local/central entry disagreement")
            }
            val dataStart = checkedAdd(zip.filePointer, localNameLen + localExtraLen.toLong(),
                directoryOffset, "local entry bounds")
            val localName = ByteArray(localNameLen)
            zip.readFully(localName)
            if (!localName.contentEquals(nameBytes)) fail("local/central entry name mismatch")
            checkExtraFields(zip, localExtraLen, dataStart)
            if (flags and 8 == 0 &&
                (localCrc != crc || localCompressed != compressed || localSize != size)
            ) fail("local entry content descriptors disagree")
            val dataEnd = checkedAdd(dataStart, compressed, directoryOffset, "compressed entry")
            occupied.add(localOffset to dataEnd)
            zip.seek(nextCentral)
            result.add(Entry(name, isDirectory, size, compressed, crc, method))
        }
        if (zip.filePointer != eocd) fail("central directory count/length mismatch")
        val byOffset = occupied.sortedBy { it.first }
        if (byOffset.first().first != 0L) fail("prepended or self-extracting ZIP payload")
        for (i in 1 until byOffset.size) {
            if (byOffset[i].first < byOffset[i - 1].second) fail("overlapping local entries")
        }
        if (apks == 0) fail("archive has no APKs")
        result
    }
}
