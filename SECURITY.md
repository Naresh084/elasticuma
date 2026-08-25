# Security policy

Report security issues privately through the repository's GitHub Security
Advisories page before opening a public issue. Do not include a live exploit or
secret in a public discussion.

The local inference server binds to `127.0.0.1` in native code and exposes no
host override in the public wrapper. It has no authentication or TLS: do not
proxy, tunnel, patch, or otherwise expose it to a LAN or WAN. Model repositories
are data inputs and may not execute remote code. ElasticUMA pins revisions and
does not enable `trust_remote_code` in its model-store path.

The runtime bootstrap verifies a pinned upstream commit and the complete staged
patch hash. It refuses extra source changes rather than building an ambiguous
runtime. Review community model profiles as untrusted configuration even though
the schema rejects unknown fields and mutable revisions.
