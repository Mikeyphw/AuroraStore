/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.installer.verification

import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.charset.Charset
import java.util.zip.ZipFile

/** Minimal, bounds-checked parser for the manifest identity of base AND split APK files. */
internal object BinaryApkManifest {
    data class Identity(val packageName: String, val versionCode: Long, val splitName: String?)

    fun read(file: File): Identity {
        val bytes = ZipFile(file).use { archive ->
            val manifest = archive.getEntry("AndroidManifest.xml")
                ?: throw ApkVerificationException("APK has no AndroidManifest.xml: ${file.name}")
            if (manifest.size > 2 * 1024 * 1024) {
                throw ApkVerificationException("APK manifest is unexpectedly large")
            }
            archive.getInputStream(manifest).use { stream ->
                val output = ByteArrayOutputStream()
                val block = ByteArray(8192)
                while (true) {
                    val read = stream.read(block)
                    if (read < 0) break
                    if (output.size() + read > 2 * 1024 * 1024) {
                        throw ApkVerificationException("APK manifest exceeds safe size limit")
                    }
                    output.write(block, 0, read)
                }
                output.toByteArray()
            }
        }
        val buffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
        requireChunk(buffer, 0, 0x0003, bytes.size)
        val strings = mutableListOf<String>()
        var offset = 8
        while (offset + 8 <= bytes.size) {
            val type = ushort(buffer, offset)
            val header = ushort(buffer, offset + 2)
            val size = int(buffer, offset + 4)
            if (size < header || header < 8 || offset.toLong() + size > bytes.size) {
                throw ApkVerificationException("APK manifest has invalid chunk bounds")
            }
            when (type) {
                0x0001 -> strings.addAll(stringPool(buffer, offset, header, size))
                0x0102 -> {
                    if (header < 36 || strings.isEmpty()) {
                        throw ApkVerificationException("APK manifest has invalid element metadata")
                    }
                    if (readString(strings, int(buffer, offset + 20)) == "manifest") {
                        val attributeStart = ushort(buffer, offset + 24)
                        val attributeSize = ushort(buffer, offset + 26)
                        val attributeCount = ushort(buffer, offset + 28)
                        if (attributeSize < 20 || attributeCount > 100) {
                            throw ApkVerificationException("APK manifest has invalid attributes")
                        }
                        val attrs = mutableMapOf<String, Pair<Int, Long>>()
                        for (i in 0 until attributeCount) {
                            val position = offset.toLong() + 16 + attributeStart + i * attributeSize
                            if (position + 20 > offset.toLong() + size) {
                                throw ApkVerificationException("APK manifest attributes exceed chunk")
                            }
                            val p = position.toInt()
                            val key = readString(strings, int(buffer, p + 4))
                            val raw = int(buffer, p + 8)
                            val dataType = bytes[p + 15].toInt() and 0xff
                            val value = int(buffer, p + 16)
                            val stringValue = if (raw >= 0) raw else if (dataType == 3) value else -1
                            attrs[key] = stringValue to (value.toLong() and 0xffffffffL)
                        }
                        val packageIndex = attrs["package"]?.first ?: -1
                        val pkg = readString(strings, packageIndex)
                        if (!pkg.matches(Regex("[A-Za-z_][A-Za-z0-9_]*(\\.[A-Za-z_][A-Za-z0-9_]*)+"))) {
                            throw ApkVerificationException("APK package identity is missing or invalid")
                        }
                        val code = attrs["versionCode"]?.second
                            ?: throw ApkVerificationException("APK version code is missing")
                        val major = attrs["versionCodeMajor"]?.second ?: 0L
                        val version = (major shl 32) or code
                        if (version <= 0) throw ApkVerificationException("APK version is invalid")
                        val split = attrs["split"]?.first?.let { readString(strings, it) }
                        return Identity(pkg, version, split)
                    }
                }
            }
            offset += size
        }
        throw ApkVerificationException("APK has no readable manifest declaration")
    }

    private fun stringPool(buf: ByteBuffer, start: Int, header: Int, size: Int): List<String> {
        if (header < 28) throw ApkVerificationException("Invalid APK string table")
        val count = int(buf, start + 8)
        val flags = int(buf, start + 16)
        val stringsStart = int(buf, start + 20)
        if (count < 0 || count > 50000 || stringsStart < header || header.toLong() + 4L * count > size) {
            throw ApkVerificationException("Invalid APK string table bounds")
        }
        val utf8 = flags and 0x100 != 0
        return (0 until count).map { i ->
            val relative = int(buf, start + header + 4 * i)
            val position = start.toLong() + stringsStart + relative
            if (relative < 0 || position >= start.toLong() + size) {
                throw ApkVerificationException("APK string offset is out of bounds")
            }
            var at = position.toInt()
            fun length8(): Int {
                val first = buf.get(at++).toInt() and 0xff
                return if (first and 0x80 == 0) first else ((first and 0x7f) shl 8) or
                    (buf.get(at++).toInt() and 0xff)
            }
            fun length16(): Int {
                val first = ushort(buf, at)
                at += 2
                return if (first and 0x8000 == 0) first else {
                    val second = ushort(buf, at)
                    at += 2
                    ((first and 0x7fff) shl 16) or second
                }
            }
            val byteCount: Int
            val charset: Charset
            if (utf8) {
                length8()
                byteCount = length8()
                charset = Charsets.UTF_8
            } else {
                byteCount = length16() * 2
                charset = Charsets.UTF_16LE
            }
            if (byteCount < 0 || at.toLong() + byteCount > start.toLong() + size) {
                throw ApkVerificationException("Invalid APK encoded string length")
            }
            String(buf.array(), at, byteCount, charset)
        }
    }

    private fun readString(values: List<String>, index: Int): String =
        values.getOrNull(index) ?: ""

    private fun requireChunk(buf: ByteBuffer, offset: Int, type: Int, minSize: Int) {
        if (buf.limit() < 8 || ushort(buf, offset) != type ||
            int(buf, offset + 4) != minSize) {
            throw ApkVerificationException("APK manifest is not a valid compiled Android manifest")
        }
    }

    private fun ushort(buf: ByteBuffer, index: Int): Int = buf.getShort(index).toInt() and 0xffff
    private fun int(buf: ByteBuffer, index: Int): Int = buf.getInt(index)
}
