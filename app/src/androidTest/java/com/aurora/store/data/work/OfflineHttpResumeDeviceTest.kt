/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.data.work

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.google.common.truth.Truth.assertThat
import java.io.Closeable
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.net.InetAddress
import java.net.Proxy
import java.net.ServerSocket
import java.net.Socket
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import kotlin.concurrent.thread
import okhttp3.OkHttpClient
import okhttp3.Request
import org.junit.Test
import org.junit.runner.RunWith

/** Real offline HTTP sockets; uses the production resume policy, not Play credentials. */
@RunWith(AndroidJUnit4::class)
class OfflineHttpResumeDeviceTest {
    private val client = OkHttpClient.Builder().proxy(Proxy.NO_PROXY).build()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext

    @Test
    fun validPartialResponseResumesBytePerfectly() {
        val file = File.createTempFile("r1d2-append", ".tmp", context.cacheDir)
        try {
            file.writeText("ABCD")
            LocalServer { socket, headers ->
                assertThat(headers["range"]).isEqualTo("bytes=4-")
                socket.reply(206, "EFGHIJ", "bytes 4-9/10")
            }.use { server ->
                client.newCall(request(server.url, 4L)).execute().use { response ->
                    assertThat(response.code).isEqualTo(206)
                    assertThat(ResumeRangePolicy.matches(response.header("Content-Range"), 4L))
                        .isTrue()
                    FileOutputStream(file, true).use { response.body.byteStream().copyTo(it) }
                }
            }
            assertThat(file.readText()).isEqualTo("ABCDEFGHIJ")
        } finally {
            file.delete()
        }
    }

    @Test
    fun ignoredRangeRestartsInsteadOfAppending() {
        val file = File.createTempFile("r1d2-reset", ".tmp", context.cacheDir)
        try {
            file.writeText("ABCD")
            LocalServer { socket, _ -> socket.reply(200, "ABCDEFGHIJ") }.use { server ->
                client.newCall(request(server.url, 4L)).execute().use { response ->
                    assertThat(response.code).isEqualTo(200)
                    FileOutputStream(file, false).use { response.body.byteStream().copyTo(it) }
                }
            }
            assertThat(file.readText()).isEqualTo("ABCDEFGHIJ")
        } finally {
            file.delete()
        }
    }

    @Test
    fun wrongRangeOffsetNeverAppends() {
        LocalServer { socket, _ -> socket.reply(206, "DEFGHIJ", "bytes 3-9/10") }.use {
            client.newCall(request(it.url, 4L)).execute().use { response ->
                assertThat(ResumeRangePolicy.matches(response.header("Content-Range"), 4L))
                    .isFalse()
            }
        }
    }

    @Test
    fun invalidRangeBoundsNeverAppend() {
        LocalServer { socket, _ -> socket.reply(206, "EFG", "bytes 4-6/5") }.use {
            client.newCall(request(it.url, 4L)).execute().use { response ->
                assertThat(ResumeRangePolicy.matches(response.header("Content-Range"), 4L))
                    .isFalse()
            }
        }
    }

    @Test
    fun http416RequiresSafeRestart() {
        LocalServer { socket, headers ->
            assertThat(headers["range"]).isEqualTo("bytes=99-")
            socket.reply(416, "")
        }.use {
            client.newCall(request(it.url, 99L)).execute().use { response ->
                assertThat(ResumeRangePolicy.requiresRestart(response.code, 99L)).isTrue()
            }
        }
    }

    @Test
    fun cancellingActiveCallUnblocksBodyRead() {
        val ready = CountDownLatch(1)
        val release = CountDownLatch(1)
        val executor = Executors.newSingleThreadExecutor()
        try {
            LocalServer { socket, _ ->
                socket.getOutputStream().apply {
                    write("HTTP/1.1 200 OK\r\nContent-Length: 1048576\r\n".toByteArray())
                    write("Connection: close\r\n\r\n".toByteArray())
                    flush()
                }
                ready.countDown()
                release.await(10L, TimeUnit.SECONDS)
            }.use { server ->
                val call = client.newCall(request(server.url, 0L))
                val result = executor.submit<Boolean> {
                    try {
                        call.execute().use { it.body.byteStream().read() }
                        false
                    } catch (_: IOException) {
                        true
                    }
                }
                assertThat(ready.await(10L, TimeUnit.SECONDS)).isTrue()
                call.cancel()
                assertThat(result.get(10L, TimeUnit.SECONDS)).isTrue()
            }
        } finally {
            release.countDown()
            executor.shutdownNow()
        }
    }

    private fun request(url: String, offset: Long): Request = Request.Builder().url(url)
        .apply { if (offset > 0L) header("Range", "bytes=$offset-") }
        .build()

    private class LocalServer(
        private val handler: (Socket, Map<String, String>) -> Unit
    ) : Closeable {
        private val listener = ServerSocket(0, 1, InetAddress.getByName("127.0.0.1"))
        val url = "http://127.0.0.1:${listener.localPort}/fixture.apk"
        private val finished = CountDownLatch(1)
        private val serving = thread(isDaemon = true) {
            try {
                listener.accept().use { socket ->
                    socket.soTimeout = 10_000
                    val reader = socket.getInputStream().bufferedReader(Charsets.US_ASCII)
                    reader.readLine()
                    val headers = mutableMapOf<String, String>()
                    while (true) {
                        val line = reader.readLine() ?: break
                        if (line.isEmpty()) break
                        headers[line.substringBefore(':').lowercase()] =
                            line.substringAfter(':').trim()
                    }
                    handler(socket, headers)
                }
            } catch (_: IOException) {
                // Closed by the test when the local response completes or is cancelled.
            } finally {
                finished.countDown()
            }
        }

        override fun close() {
            listener.close()
            finished.await(12L, TimeUnit.SECONDS)
            serving.join(1_000L)
        }
    }

    private fun Socket.reply(code: Int, body: String, range: String? = null) {
        val bytes = body.toByteArray(Charsets.UTF_8)
        val reason = when (code) {
            200 -> "OK"
            206 -> "Partial Content"
            else -> "Range Not Satisfiable"
        }
        val rangeHeader = range?.let { "Content-Range: $it\r\n" }.orEmpty()
        val header = "HTTP/1.1 $code $reason\r\nContent-Length: ${bytes.size}\r\n" +
            rangeHeader + "Connection: close\r\n\r\n"
        getOutputStream().apply {
            write(header.toByteArray(Charsets.US_ASCII))
            write(bytes)
            flush()
        }
    }
}
