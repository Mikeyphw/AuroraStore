/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.data.artifact

import com.aurora.store.data.installer.verification.ApkVerificationException
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.charset.CodingErrorAction
import java.util.zip.ZipFile

/** Restricted Android binary XML reader for <uses-split android:name="..."/>.
 * No network, dynamic reflection, bundletool protobuf trust, or root privileges.
 * Read only AFTER a platform v2+ signature has been independently authenticated.
 */
internal object ArtifactSignedManifestDependencies {
    private const val MAX = 2 * 1024 * 1024
    private const val ANDROID_NS = "http://schemas.android.com/apk/res/android"
    private fun fail(): Nothing = throw ApkVerificationException("Signed manifest dependency metadata is invalid")
    private fun u16(b: ByteBuffer, p: Int): Int {
        if (p < 0 || p > b.limit() - 2) fail()
        return b.getShort(p).toInt() and 0xffff
    }
    private fun i32(b: ByteBuffer, p: Int): Int {
        if (p < 0 || p > b.limit() - 4) fail()
        return b.getInt(p)
    }
    private fun length8(b: ByteBuffer, at: IntArray, limit: Int): Int {
        if (at[0] >= limit) fail()
        val first = b.get(at[0]++).toInt() and 255
        if (first and 0x80 == 0) return first
        if (at[0] >= limit) fail()
        return ((first and 127) shl 8) or (b.get(at[0]++).toInt() and 255)
    }
    private fun length16(b: ByteBuffer, at: IntArray, limit: Int): Int {
        if (at[0] > limit - 2) fail()
        val first = u16(b, at[0]); at[0] += 2
        if (first and 0x8000 == 0) return first
        if (at[0] > limit - 2) fail()
        val second = u16(b, at[0]); at[0] += 2
        return ((first and 0x7fff) shl 16) or second
    }
    private fun decodeStrings(b: ByteBuffer, pos: Int, header: Int, size: Int): List<String> {
        if (header < 28) fail()
        val count = i32(b, pos + 8)
        val flags = i32(b, pos + 16)
        val start = i32(b, pos + 20)
        if (count !in 0..50000 || start < header ||
            header.toLong() + 4L * count > size.toLong() || start >= size
        ) fail()
        val utf8 = flags and 0x100 != 0
        val end = pos + size
        return (0 until count).map { index ->
            val relative = i32(b, pos + header + 4 * index)
            if (relative < 0 || pos.toLong() + start + relative >= end) fail()
            val at = intArrayOf(pos + start + relative)
            val bytes: Int = if (utf8) {
                length8(b, at, end) // utf16 char count
                length8(b, at, end)
            } else {
                val chars = length16(b, at, end)
                if (chars > MAX / 2) fail()
                chars * 2
            }
            if (bytes < 0 || bytes > 8192 || at[0].toLong() + bytes + (if (utf8) 1 else 2) > end) fail()
            val terminator = at[0] + bytes
            if ((b.get(terminator).toInt() != 0) || (!utf8 && b.get(terminator + 1).toInt() != 0)) fail()
            val input = b.duplicate().apply { position(at[0]); limit(terminator) }
            val charset = if (utf8) Charsets.UTF_8 else Charsets.UTF_16LE
            try {
                charset.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
                    .onUnmappableCharacter(CodingErrorAction.REPORT)
                    .decode(input).toString()
            } catch (_: Exception) { fail() }
        }
    }

    /** Pure compiled-XML parser, also exposed for adversarial JVM fixtures. */
    fun parse(compiled: ByteArray): String? {
        if (compiled.size !in 8..MAX) fail()
        val b = ByteBuffer.wrap(compiled).order(ByteOrder.LITTLE_ENDIAN)
        if (u16(b, 0) != 0x0003 || i32(b, 4) != compiled.size) fail()
        var offset = 8
        var strings: List<String>? = null
        var required: String? = null
        while (offset < compiled.size) {
            if (offset > compiled.size - 8) fail()
            val type = u16(b, offset)
            val header = u16(b, offset + 2)
            val size = i32(b, offset + 4)
            if (header < 8 || size < header || offset.toLong() + size > compiled.size) fail()
            if (type == 0x0001) {
                if (strings != null) fail()
                strings = decodeStrings(b, offset, header, size)
            }
            if (type == 0x0102) {
                if (header != 16 || size < 36) fail()
                val table = strings ?: fail()
                fun string(index: Int): String? = if (index == -1) null else table.getOrNull(index) ?: fail()
                if (string(i32(b, offset + 20)) == "uses-split") {
                    val attrStart = u16(b, offset + 24)
                    val attrSize = u16(b, offset + 26)
                    val attrCount = u16(b, offset + 28)
                    if (attrStart < 20 || attrSize < 20 || attrCount > 100) fail()
                    if (required != null) fail() // Ambiguous duplicate declaration
                    var dependency: String? = null
                    for (i in 0 until attrCount) {
                        val location = offset.toLong() + 16 + attrStart + i.toLong() * attrSize
                        if (location + 20 > offset.toLong() + size) fail()
                        val p = location.toInt()
                        if (string(i32(b, p)) == ANDROID_NS && string(i32(b, p + 4)) == "name") {
                            if (dependency != null) fail()
                            val raw = i32(b, p + 8)
                            val typeOfValue = b.get(p + 15).toInt() and 255
                            val index = if (raw >= 0) raw else if (typeOfValue == 3) i32(b, p + 16) else -1
                            dependency = string(index) ?: fail()
                        }
                    }
                    required = dependency ?: fail()
                }
            }
            offset += size
        }
        if (offset != compiled.size || strings == null) fail()
        return required
    }

    fun read(file: File): String? = ZipFile(file).use { zip ->
        val manifest = zip.getEntry("AndroidManifest.xml") ?: fail()
        if (manifest.size > MAX || manifest.size < 8) fail()
        val bytes = zip.getInputStream(manifest).use { stream ->
            val output = java.io.ByteArrayOutputStream()
            val buffer = ByteArray(8192)
            while (true) {
                val n = stream.read(buffer)
                if (n < 0) break
                if (n == 0 || output.size().toLong() + n > MAX) fail()
                output.write(buffer, 0, n)
            }
            output.toByteArray()
        }
        parse(bytes)
    }
}
