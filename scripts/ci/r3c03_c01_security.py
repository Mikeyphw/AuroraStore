#!/usr/bin/env python3
"""R3C-03 C01 source safety checks, independent of Kotlin formatting."""
import re


def compact(source):
    # Source proof must never count Kotlin comments as implemented behavior.
    without_comments = re.sub(r'/\*[\s\S]*?\*/|//[^\n]*', '', source)
    return re.sub(r'\s+', '', without_comments)


def validate_sources(worker, classifier, dao, fingerprint, migration):
    w = compact(worker)
    c = compact(classifier)
    d = compact(dao)
    f = compact(fingerprint)
    m = compact(migration)

    def must(source, marker, reason):
        if compact(marker) not in source:
            raise ValueError('R3C03_C01_SECURITY_REFUSED: ' + reason)

    def forbidden(source, marker, reason):
        if compact(marker) in source:
            raise ValueError('R3C03_C01_SECURITY_REFUSED: ' + reason)

    must(w, 'is PlayException.RateLimited, is PlayException.ServerError, is NoNetworkException',
         'transient Play quota and server faults require retry/backoff')
    must(c, 'is PlayException.RateLimited -> PlayExactVersionOutcomePolicy.Failure.RATE_LIMITED',
         'quota must be classified separately')
    must(c, 'is PlayException.ServerError -> PlayExactVersionOutcomePolicy.Failure.TEMPORARY_SERVER_ERROR',
         'server error must not prove unavailability')
    must(c, 'is PlayException.AppNotSupported, is PlayException.NotFound,',
         'device restriction and package not found are ambiguous')
    must(c, 'is PlayException.NoFilesAvailable, is PlayException.Unknown -> '
         'PlayExactVersionOutcomePolicy.Failure.AMBIGUOUS_PLAY_REJECTION',
         'unknown and empty-file-list responses must remain ambiguous')
    forbidden(c, 'EXACT_VERSION_UNAVAILABLE', 'classifier must not manufacture unavailable proof')
    must(w, 'return PlayAccountFingerprint.hmacHex(key, id)',
         'selected account must be pseudonymized before storage')
    must(f, 'require(secret.size == 32)', 'weak fingerprint key size')
    must(f, 'Mac.getInstance("HmacSHA256")', 'HMAC is required')
    must(w, 'val key = selectedKey.copy(variant = "${selectedKey.variant};lane:$route")',
         'persist effective anonymous vs authenticated resolution lane')
    must(w, 'deliveryClient === noAuthPlayClient -> "anonymous"',
         'actual anonymous client lane must be recorded')
    must(w, 'selectedAccount = selectedPlayAccount ?: return',
         'account selection must be checked inside Room transaction')
    must(w, 'storePlayOutcome("URLS_RESOLVED", resolved.size)',
         'record actual non-empty URL resolution only')
    must(w, 'PlayDeliveryFailureClassifier.classify(exception)',
         'source failures must use the safe classifier')
    if w.count(compact('PlayDeliveryFailureClassifier.classify(exception)')) != 2:
        raise ValueError('R3C03_C01_SECURITY_REFUSED: both auth and resolve failures must classify')
    must(w, 'R.string.r3c03_delivery_not_proven_unavailable',
         'ambiguous Play error must not falsely claim version absent')
    forbidden(w, 'R.string.download_version_unavailable',
              'old false unavailable message remains')
    must(d, '@Transaction suspend fun accept(', 'evidence CAS must be transactional')
    must(d, 'downloadedAt = :attemptGeneration', 'worker generation must match Room')
    must(d, 'currentProcessingAttempt(packageName, versionCode, attemptGeneration) != 1',
         'stale, cancelled, replaced or completed workers must be refused')
    must(d, 'selectedAccountIdentity(packageName) != selectedAccount',
         'account changes must invalidate evidence')
    must(d, 'stored.key() != key', 'same-generation foreign variants must be refused')
    must(d, 'PlayExactVersionOutcomePolicy.reduce(key, prior, event)',
         'transitions must use fail-closed evidence policy')
    forbidden(d, 'Event.ExactVersionRefused', 'C01 cannot manufacture Play absence')
    forbidden(d, 'Event.R3bVerifiedSet', 'C01 cannot fabricate verified APK bytes')
    must(m, 'val MIGRATION_15_16 = object : Migration(15, 16)',
         'Room migration must preserve version 15')
    must(m, 'CREATE TABLE IF NOT EXISTS `play_delivery_evidence`',
         'Room migration must add evidence table')
    return True
