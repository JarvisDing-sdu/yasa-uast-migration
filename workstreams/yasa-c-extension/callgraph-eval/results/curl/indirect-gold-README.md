# Frozen curated libcurl indirect-call audit

The source and build configuration were read independently, without reading
Yasa C or CodeGraph C output. `indirect-gold.json` was frozen before notifying
the person running the comparison that it was available.

Frozen SHA256:

`64d8f77f8e0599683012cbf19fa01be3c4aa12b176e2f024373de49e9dcf41e1`

This is **11 selected sites and 25 expected site-target edges**, spanning five
internal mechanisms. All 25 remain distinct when reduced to caller-target
pairs. There are 22 distinct target functions. Report any resulting score as
**curated indirect subset recall**, never as overall libcurl indirect recall.
Selection favored clearly bounded target provenance and several mechanisms;
it is not a random or exhaustive sample.

The selected sites are:

- MIME encoder read and size dispatches, at `lib/mime.c:778` and `:1640`.
  An encoding name selects an immutable table row; applications cannot supply
  the encode/size implementation. Four read and three size implementations
  result after deduplicating table rows.
- MD5 context initialization, update, and finalization, at `lib/md5.c:593`,
  `:605`, and `:612`. Every internal parameter origin is `Curl_DIGEST_MD5`.
- Three representative HMAC initialization/update/finalization expressions,
  at `lib/hmac.c:77`, `:106`, and `:119`. The valid internal parameter origins
  are `Curl_HMAC_MD5` and `Curl_HMAC_SHA256`. The defined but unused
  `Curl_HMAC_SHA512_256` object is not assumed to reach these sites.
- Generic pingpong state-machine and response-parser dispatches, at
  `lib/pingpong.c:116` and `:307`. Exactly four enabled protocols register
  callbacks: FTP, IMAP, POP3, and SMTP. Each object retains its own protocol's
  pair; a generic dispatch site has the union across those valid objects.
- The internal FTP wildcard destructor, at `lib/ftplistparser.c:197`. Its only
  non-null source is `lib/ftp.c::wc_data_dtor`.

For the configured build, the MD5 and SHA256 callback wrappers are the OpenSSL
branches. FTP, IMAP, POP3, SMTP, MIME, and digest authentication are enabled.
HTTPSIG is disabled. The session-cache HMAC call at `vtls/vtls_scache.c:809`
is active. The additional source references at `:1165` and `:1203` are under
disabled `USE_SSLS_EXPORT`; this does not affect the two-object target bound.
The AWS helper macro expands at its call sites, rather than leaving its
definition line in preprocessed output.

`compiler_preprocessing_verification` in the gold records 33 checks showing
that all 11 selected calls and 22 target definitions survive preprocessing
using the exact compile database command. All 14 inspected translation units
preprocess successfully without diagnostics. The `.i` files retain source
line directives and are saved under `preprocessed/` for review.

File guide:

- `indirect-gold.json`: authoritative source identities, locations, target
  sets, execution guards, excerpts, assignment/initializer provenance, scope,
  build hashes, and active-code checks.
- `indirect-gold.sha256` and `freeze.json`: freeze declaration and checksum.
- `expected-edges.tsv`: derived flat view convenient for scoring.
- `build_audit.py`: evidence-pack generator. Re-running updates creation and
  freeze timestamps, so do not run it over the frozen comparison artifact.

Columns in the gold are 1-based starts of the original source callee
expressions. Matching a tool's caller-target-only graph is possible because
the selected 25 caller-target pairs are unique. A tool that gives additional
targets has not thereby proved them correct; a tool that omits an expected
target has missed an edge in this curated subset. This pack supplies positive
ground truth for the chosen sites and does not establish false-positive
labels elsewhere.

The excluded callback inventory shows MIME read/seek/free dispatches whose
public registration API permits arbitrary application callbacks. Internal
targets on some branches cannot bound those whole sites. These entries do
not enter the 11-site denominator. Arbitrary external calls to hidden private
`Curl_*` routines with forged contexts and direct writes to private structs
are outside the supported-API scope of this audit.
