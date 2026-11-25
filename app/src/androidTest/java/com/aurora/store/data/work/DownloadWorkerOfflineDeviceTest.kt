/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.work

import androidx.hilt.work.HiltWorkerFactory
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.work.Data
import androidx.work.ListenableWorker
import androidx.work.testing.TestListenableWorkerBuilder
import com.aurora.store.data.model.DownloadStatus
import com.aurora.store.data.room.download.Download
import com.aurora.store.data.room.download.DownloadDao
import com.google.common.truth.Truth.assertThat
import dagger.hilt.android.testing.HiltAndroidRule
import dagger.hilt.android.testing.HiltAndroidTest
import java.io.Closeable
import java.net.InetAddress
import java.net.ServerSocket
import java.net.Socket
import java.security.MessageDigest
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import javax.inject.Inject
import kotlin.concurrent.thread
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Executes the real Hilt-created DownloadWorker with offline loopback responses. */
@HiltAndroidTest
@RunWith(AndroidJUnit4::class)
class DownloadWorkerOfflineDeviceTest {
    @get:Rule
    val hiltRule = HiltAndroidRule(this)

    @Inject
    lateinit var workerFactory: HiltWorkerFactory

    @Inject
    lateinit var dao: DownloadDao

    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val touched = mutableListOf<String>()

    @Before
    fun setUp() {
        hiltRule.inject()
    }

    @After
    fun cleanUp() = runBlocking {
        touched.forEach { packageName ->
            dao.delete(packageName)
            R1EOfflineGate.file(context, packageName, ATTEMPT).delete()
            R1EOfflineGate.file(context, packageName, ATTEMPT).let { file ->
                java.io.File(file.absolutePath + ".tmp").delete()
            }
        }
    }

    @Test
    fun realWorkerDownloadsAndVerifiesBytesWithoutInstalling() = runBlocking {
        val pkg = seed("complete")
        LocalHttpServer(listOf { socket, _ -> socket.reply(200, PAYLOAD) }).use { server ->
            val result = runWorker(input(pkg, server.url))
            assertThat(result).isEqualTo(ListenableWorker.Result.success())
            assertThat(dao.getDownload(pkg).status).isEqualTo(DownloadStatus.COMPLETED)
            assertThat(R1EOfflineGate.file(context, pkg, ATTEMPT).readText()).isEqualTo(PAYLOAD)
            assertThat(server.hits.get()).isEqualTo(1)
        }
    }

    @Test
    fun truncatedResponseRetriesThenResumesSameAttemptExactly() = runBlocking {
        val pkg = seed("resume")
        LocalHttpServer(
            listOf(
                { socket, _ -> socket.reply(200, "ABCD", declaredSize = 10) },
                { socket, headers ->
                    assertThat(headers["range"]).isEqualTo("bytes=4-")
                    socket.reply(206, "EFGHIJ", range = "bytes 4-9/10")
                }
            )
        ).use { server ->
            val request = input(pkg, server.url)
            assertThat(runWorker(request)).isEqualTo(ListenableWorker.Result.retry())
            val file = R1EOfflineGate.file(context, pkg, ATTEMPT)
            assertThat(java.io.File(file.absolutePath + ".tmp").readText()).isEqualTo("ABCD")
            assertThat(runWorker(request)).isEqualTo(ListenableWorker.Result.success())
            assertThat(file.readText()).isEqualTo(PAYLOAD)
            assertThat(dao.getDownload(pkg).status).isEqualTo(DownloadStatus.COMPLETED)
            assertThat(server.hits.get()).isEqualTo(2)
        }
    }

    @Test
    fun invalidContentRangeDeletesPartialAndRequestsRetry() = runBlocking {
        val pkg = seed("wrong_range")
        val file = R1EOfflineGate.file(context, pkg, ATTEMPT)
        java.io.File(file.absolutePath + ".tmp").writeText("ABCD")
        LocalHttpServer(
            listOf { socket, _ -> socket.reply(206, "DEFGHIJ", range = "bytes 3-9/10") }
        ).use { server ->
            assertThat(runWorker(input(pkg, server.url)))
                .isEqualTo(ListenableWorker.Result.retry())
            assertThat(java.io.File(file.absolutePath + ".tmp").exists()).isFalse()
            assertThat(file.exists()).isFalse()
        }
    }

    @Test
    fun unsatisfiableRangeRemovesPartialAndRequestsRetry() = runBlocking {
        val pkg = seed("range_416")
        val file = R1EOfflineGate.file(context, pkg, ATTEMPT)
        java.io.File(file.absolutePath + ".tmp").writeText("ABCD")
        LocalHttpServer(listOf { socket, _ -> socket.reply(416, "") }).use { server ->
            assertThat(runWorker(input(pkg, server.url)))
                .isEqualTo(ListenableWorker.Result.retry())
            assertThat(java.io.File(file.absolutePath + ".tmp").exists()).isFalse()
        }
    }

    @Test
    fun shaMismatchRejectsPayloadWithoutInstallHandoff() = runBlocking {
        val pkg = seed("bad_digest")
        LocalHttpServer(listOf { socket, _ -> socket.reply(200, "ABCDxxxxIJ") }).use { server ->
            // The worker persists FAILED, then returns terminal Success to avoid retrying
            // a non-recoverable checksum mismatch. This is production onFailure semantics.
            assertThat(runWorker(input(pkg, server.url)))
                .isEqualTo(ListenableWorker.Result.success())
            assertThat(dao.getDownload(pkg).status).isEqualTo(DownloadStatus.FAILED)
            assertThat(R1EOfflineGate.file(context, pkg, ATTEMPT).exists()).isFalse()
            assertThat(server.hits.get()).isEqualTo(1)
        }
    }

    @Test
    fun obsoleteAttemptDoesNotReachNetworkOrMutateRow() = runBlocking {
        val pkg = seed("obsolete")
        LocalHttpServer(emptyList()).use { server ->
            val data = input(pkg, server.url, attempt = ATTEMPT - 1L)
            assertThat(runWorker(data)).isEqualTo(ListenableWorker.Result.success())
            assertThat(dao.getDownload(pkg).status).isEqualTo(DownloadStatus.QUEUED)
            assertThat(server.hits.get()).isEqualTo(0)
        }
    }

    @Test
    fun cancelledAttemptIsNotResurrectedOrDownloaded() = runBlocking {
        val pkg = seed("cancelled", DownloadStatus.CANCELLED)
        LocalHttpServer(emptyList()).use { server ->
            assertThat(runWorker(input(pkg, server.url)))
                .isEqualTo(ListenableWorker.Result.success())
            assertThat(dao.getDownload(pkg).status).isEqualTo(DownloadStatus.CANCELLED)
            assertThat(server.hits.get()).isEqualTo(0)
        }
    }

    @Test
    fun fixtureRequestCannotUseExternalHost() = runBlocking {
        val pkg = seed("host_denied")
        val data = input(pkg, "https://example.com/download.apk")
        assertThat(runWorker(data)).isEqualTo(ListenableWorker.Result.failure())
        assertThat(dao.getDownload(pkg).status).isEqualTo(DownloadStatus.QUEUED)
    }

    private suspend fun seed(name: String, status: DownloadStatus = DownloadStatus.QUEUED): String {
        val pkg = "com.aurora.r1e.fixture.$name"
        touched.add(pkg)
        dao.insert(
            Download(
                packageName = pkg,
                versionCode = VERSION,
                offerType = 0,
                isInstalled = false,
                displayName = "Offline worker test",
                iconURL = "",
                size = PAYLOAD.length.toLong(),
                id = 0,
                status = status,
                progress = 0,
                speed = 0L,
                timeRemaining = 0L,
                totalFiles = 0,
                downloadedFiles = 0,
                fileList = emptyList(),
                sharedLibs = emptyList(),
                downloadedAt = ATTEMPT
            )
        )
        return pkg
    }

    private fun input(pkg: String, url: String, attempt: Long = ATTEMPT): Data = Data.Builder()
        .putString("PACKAGE_NAME", pkg)
        .putLong("VERSION_CODE", VERSION)
        .putLong("ATTEMPT_KEY", attempt)
        .putBoolean(R1EOfflineGate.ENABLED, true)
        .putString(R1EOfflineGate.URL, url)
        .putLong(R1EOfflineGate.SIZE, PAYLOAD.length.toLong())
        .putString(R1EOfflineGate.SHA256, digest(PAYLOAD))
        .build()

    private suspend fun runWorker(data: Data): ListenableWorker.Result {
        val worker = TestListenableWorkerBuilder<DownloadWorker>(context)
            .setWorkerFactory(workerFactory)
            .setInputData(data)
            .build()
        return worker.doWork()
    }

    private fun digest(value: String): String = MessageDigest.getInstance("SHA-256")
        .digest(value.toByteArray(Charsets.UTF_8))
        .joinToString("") { byte -> "%02x".format(byte.toInt() and 0xff) }

    private class LocalHttpServer(
        private val responses: List<(Socket, Map<String, String>) -> Unit>
    ) : Closeable {
        private val listener = ServerSocket(0, 8, InetAddress.getByName("127.0.0.1"))
        val url: String = "http://127.0.0.1:${listener.localPort}/fixture.apk"
        val hits = AtomicInteger(0)
        private val complete = CountDownLatch(1)
        private val thread = thread(isDaemon = true) {
            try {
                responses.forEach { response ->
                    listener.accept().use { socket ->
                        socket.soTimeout = 10_000
                        val input = socket.getInputStream().bufferedReader(Charsets.US_ASCII)
                        input.readLine()
                        val headers = mutableMapOf<String, String>()
                        while (true) {
                            val line = input.readLine() ?: break
                            if (line.isBlank()) break
                            headers[line.substringBefore(':').lowercase()] =
                                line.substringAfter(':').trim()
                        }
                        hits.incrementAndGet()
                        response(socket, headers)
                    }
                }
            } catch (_: java.io.IOException) {
                // An unopened local socket is closed during fixture cleanup.
            } finally {
                complete.countDown()
            }
        }

        override fun close() {
            listener.close()
            complete.await(12L, TimeUnit.SECONDS)
            thread.join(1000L)
        }
    }

    private fun Socket.reply(
        code: Int,
        body: String,
        range: String? = null,
        declaredSize: Int = body.length
    ) {
        val name = when (code) {
            200 -> "OK"
            206 -> "Partial Content"
            else -> "Range Not Satisfiable"
        }
        val headers = "HTTP/1.1 $code $name\r\n" +
            "Content-Length: $declaredSize\r\n" +
            range?.let { "Content-Range: $it\r\n" }.orEmpty() +
            "Connection: close\r\n\r\n"
        getOutputStream().apply {
            write(headers.toByteArray(Charsets.US_ASCII))
            write(body.toByteArray(Charsets.US_ASCII))
            flush()
        }
    }

    companion object {
        private const val VERSION = 42L
        private const val ATTEMPT = 1001L
        private const val PAYLOAD = "ABCDEFGHIJ"
    }
}
