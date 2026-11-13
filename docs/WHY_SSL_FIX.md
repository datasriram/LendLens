# Why the RBI SSL fix is necessary

The corpus discovery step was correct: it found the current NBFC direction IDs from RBI's official Master Directions index. The acquisition step failed because some discovered URLs used RBI's legacy `systemhealth.rbi.org.in` hostname, which can fail TLS validation on Windows/Python Requests.

The fix preserves the resource path and query ID but canonicalizes the hostname to `www.rbi.org.in`. It also uses the Windows trust store via `truststore` rather than bypassing certificate validation. This preserves source integrity and auditability.
