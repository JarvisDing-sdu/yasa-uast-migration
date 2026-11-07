#!/usr/bin/env python3
"""Manual level-2 verdicts for the fixed-seed sample (level2-sample.json) and their summary.

Criterion: an edge is correct if, whenever the caller executes in this configured build
(OpenSSL, zlib, proxies and websockets on; no HTTP/2, no HTTP/3, no multi-SSL), the receiver
at this call site can hold an object whose field is the target. Caller reachability itself is
not judged (as for direct calls in gold). '?' = not decidable from code reading here.
"""
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
WRITERS_AFTER_DECODER = {  # next of a content/transfer decoder (HTTP only)
    'deflate_do_write': 'y', 'error_do_write': 'y', 'gzip_do_write': 'y', 'Curl_cwriter_def_write': 'y',
    'cw_out_write': 'y', 'cw_pause_write': 'y', 'hds_cw_collect_write': 'y', 'cw_download_write': 'y',
    'cw_chunked_write': 'n', 'cw_raw_write': 'n', 'ftp_cw_lc_write': 'n', 'ws_cw_write': '?'}
R = {
    'cwriter_phase': 'writer->next is a writer of the same or a later phase (sendf.c cwriter_add); '
                     'raw is first, chunked is first in transfer-decode and never duplicated, ftp_lc only in FTP',
    'cf_top_under_hc': 'b->cf is the chain top beneath HTTPS-CONNECT: SETUP while connecting, then SSL',
    'no_http3': 'capsule filter is inserted only under USE_HTTP3 (cf-setup.c), which is off',
    'recvbuf_never_added': 'Curl_cf_recvbuf_add has no caller in lib/; placement of a recvbuf filter is unknown',
    'socket_is_leaf': 'TCP/UDP/UNIX/TCP-ACCEPT socket filters are chain leaves: cf->next is always NULL here',
    'generic_dispatch': 'generic helper over any object of this type in the build',
    'below_http_proxy': 'below HTTP-PROXY: h1-proxy (its sub-filter), SSL-PROXY, SOCKS pre-proxy, happy eyeballs, socket',
    'client_reader': 'loop stops at the CURL_CR_CLIENT reader: in, buf, null or mime',
    'single_ssl': 'CURL_WITH_MULTI_SSL is off: Curl_ssl/ssl_impl is always the OpenSSL backend',
}
site = {
    ('lib/cf-https-connect.c', 590): ('cf_top_under_hc', {'Curl_cf_def_shutdown': 'y', 'ssl_cf_shutdown': 'y', 'cf_hc_shutdown': 'n',
                                      'cf_capsule_shutdown': 'n', 'cf_socket_shutdown': 'n', 'cf_ip_happy_shutdown': '?'}),
    ('lib/cf-recvbuf.c', 64): ('recvbuf_never_added', {'cf_capsule_recv': 'n', '*': '?'}),
    ('lib/cf-setup.c', 309): ('generic_dispatch', {'*': 'y'}),
    ('lib/cf-socket.c', 1915): ('socket_is_leaf', {'*': 'n'}),
    ('lib/cfilters.c', 676): ('generic_dispatch', {'cf_capsule_query': 'n', '*': 'y'}),
    ('lib/cfilters.c', 963): ('generic_dispatch', {'*': 'y'}),
    ('lib/content_encoding.c', 287): ('cwriter_phase', WRITERS_AFTER_DECODER),
    ('lib/content_encoding.c', 318): ('cwriter_phase', {'ws_cw_flush': '?', '*': 'y'}),
    ('lib/curl_sasl.c', 524): ('generic_dispatch', {'*': 'y'}),
    ('lib/ftp.c', 436): ('cwriter_phase', {'cw_out_write': 'y', '*': 'n'}),
    ('lib/hash.c', 401): ('generic_dispatch', {'*': 'y'}),
    ('lib/http_chunks.c', 128): ('cwriter_phase', WRITERS_AFTER_DECODER),
    ('lib/http_proxy.c', 683): ('below_http_proxy', {'cf_h1_proxy_query': 'y', 'cf_ip_happy_query': 'y', 'cf_socket_query': 'y',
                                'socks_cf_query': 'y', 'ssl_cf_query': 'y', 'cf_hc_query': 'n', 'cf_http_proxy_query': 'n',
                                'cf_capsule_query': 'n', 'Curl_cf_def_query': '?'}),
    ('lib/multi.c', 1058): ('generic_dispatch', {'*': 'y'}),
    ('lib/sendf.c', 1247): ('generic_dispatch', {'*': 'y'}),
    ('lib/sendf.c', 1440): ('client_reader', {'cr_mime_total_length': 'y', 'cr_buf_total_length': 'y', 'cr_in_total_length': 'y',
                            'cr_null_total_length': 'y', '*': 'n'}),
    ('lib/url.c', 2256): ('generic_dispatch', {'*': 'y'}),
    ('lib/vtls/vtls.c', 579): ('single_ssl', {'*': 'y'}),
    ('lib/vtls/vtls.c', 713): ('single_ssl', {'*': 'y'}),
    ('lib/vtls/vtls.c', 1225): ('single_ssl', {'ossl_get_internals': 'y', 'multissl_get_internals': 'n'}),
}


def verdict(file, line, target):
    reason, table = site[(file, line)]
    name = target.split('::')[1]
    return table.get(name, table.get('*')), reason


sample = json.loads((HERE / 'level2-sample.json').read_text())['sample']
rows = []
for o in sample:
    for t in o['targets']:
        v, reason = verdict(o['file'], o['line'], t)
        assert v in ('y', 'n', '?'), (o['file'], o['line'], t)
        rows.append(dict(file=o['file'], line=o['line'], target=t, verdict=v, reason=R[reason]))


def tally(lines):
    rs = [r for r in rows if (r['file'], r['line']) in lines]
    return sum(r['verdict'] == 'y' for r in rs), sum(r['verdict'] == '?' for r in rs), len(rs)


keys = [(o['file'], o['line']) for o in sample]
y, q, n = tally(set(keys))
random.seed(1)
lo, hi = [], []
for _ in range(10000):
    b = [random.choice(keys) for _ in keys]
    rs = [r for k in b for r in rows if (r['file'], r['line']) == k]
    lo.append(sum(r['verdict'] == 'y' for r in rs) / len(rs))
    hi.append(sum(r['verdict'] != 'n' for r in rs) / len(rs))
ci = lambda xs: (sorted(xs)[249], sorted(xs)[9749])
per_line = {f'{f}:{l}': dict(zip(('correct', 'uncertain', 'pairs'), tally({(f, l)}))) for f, l in keys}
summary = dict(pairs=n, correct=y, wrong=n - y - q, uncertain=q,
               precision_lower=y / n, precision_upper=(y + q) / n,
               ci95_lower_bound=ci(lo), ci95_upper_bound=ci(hi),
               lines=len(keys), lines_all_correct=sum(v['correct'] == v['pairs'] for v in per_line.values()),
               lines_with_wrong=sum(v['correct'] + v['uncertain'] < v['pairs'] for v in per_line.values()))
(HERE / 'level2-verdicts.json').write_text(json.dumps(dict(criterion=__doc__, reasons=R, summary=summary,
                                                             per_line=per_line, rows=rows), indent=1) + '\n')
print(json.dumps(summary, indent=1))
