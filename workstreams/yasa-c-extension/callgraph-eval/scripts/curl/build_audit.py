#!/usr/bin/env python3
"""Record an analyzer-blind manual audit of selected real libcurl dispatches.

This is an evidence pack, not an automatic function-pointer target extractor.
The hand-selected bounds below come from reading the corresponding assignments
and all libcurl references to the parameter types and dispatch members.
"""
import datetime
import hashlib
import json
import re
import shlex
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
SRC = ROOT / 'work/repos/curl'
BUILD = ROOT / 'work/curl-large/build'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def evidence(file, start, end=None, why=''):
    lines = (SRC / file).read_text().splitlines()
    end = end or start
    return {'file': file, 'line': start, 'end_line': end,
            'snippet': '\n'.join(lines[start-1:end]), 'rationale': why}

def target(file, name, definition_line):
    return {'id': f'{file}::{name}', 'file': file, 'function': name,
            'definition_line': definition_line}

MD5 = {
    'init': target('lib/md5.c', 'my_md5_init', 79),
    'update': target('lib/md5.c', 'my_md5_update', 94),
    'final': target('lib/md5.c', 'my_md5_final', 101),
}
SHA256 = {
    'init': target('lib/sha256.c', 'my_sha256_init', 62),
    'update': target('lib/sha256.c', 'my_sha256_update', 76),
    'final': target('lib/sha256.c', 'my_sha256_final', 84),
}

E = {
    'mime_table': evidence('lib/mime.c', 1428, 1435,
        'The only encoder object table: five named encodings, four distinct read implementations and three distinct size implementations; the last entry is a null sentinel.'),
    'mime_assignment': evidence('lib/mime.c', 1438, 1457,
        'curl_mime_encoder assigns either null or an address from encoders; the public API accepts a name, not a function pointer.'),
    'mime_copy': evidence('lib/mime.c', 1210, 1215,
        'Duplication copies an existing encoder pointer; it introduces no new encoder implementation.'),
    'mime_guard_read': evidence('lib/mime.c', 873, 878,
        'The encoded-read routine is entered only for non-null part->encoder.'),
    'md5_params': evidence('lib/md5.c', 543, 549,
        'The only MD5_params initializer binds init/update/final to my_md5_*.'),
    'md5_store': evidence('lib/md5.c', 591, 593,
        'The MD5 context retains exactly the supplied parameter object.'),
    'md5_call_pop3': evidence('lib/pop3.c', 573, 575,
        'POP3 APOP supplies Curl_DIGEST_MD5.'),
    'md5_call_digest': evidence('lib/vauth/digest.c', 405, 407,
        'Digest auth supplies Curl_DIGEST_MD5; the other three initializations in this file do the same.'),
    'hmac_md5': evidence('lib/md5.c', 534, 541,
        'MD5 HMAC parameter object binds the three my_md5_* implementations.'),
    'hmac_sha256': evidence('lib/sha256.c', 504, 511,
        'SHA256 HMAC parameter object binds the three my_sha256_* implementations.'),
    'hmac_cram': evidence('lib/vauth/cram.c', 59, 62,
        'CRAM-MD5 creates a context with Curl_HMAC_MD5.'),
    'hmac_aws': evidence('lib/http_aws_sigv4.c', 40, 46,
        'The AWS HMAC helper macro supplies Curl_HMAC_SHA256.'),
    'hmac_scache': evidence('lib/vtls/vtls_scache.c', 807, 811,
        'TLS session-cache HMAC call supplies Curl_HMAC_SHA256; two other HMAC calls in this file do the same.'),
    'hmac_forward': evidence('lib/hmac.c', 149, 151,
        'Curl_hmacit forwards the same parameter object to Curl_HMAC_init.'),
    'hmac_store': evidence('lib/hmac.c', 61, 63,
        'The context retains the supplied hash parameter object.'),
    'hmac_final_alias': evidence('lib/hmac.c', 109, 111,
        'The finalization local alias comes from the retained context hash.'),
    'unused_sha512_params': evidence('lib/curl_sha512_256.c', 830, 846,
        'A SHA512/256 HMAC object exists, but no lib/ caller passes or otherwise references it. Its presence alone does not make it a possible target at the selected HMAC sites.'),
    'pp_macro': evidence('lib/pingpong.h', 77, 81,
        'PINGPONG_SETUP writes the protocol-specific pair of implementations.'),
    'pp_ftp': evidence('lib/ftp.c', 3540,
        why='FTP connection setup installs only FTP implementations.'),
    'pp_imap': evidence('lib/imap.c', 2289,
        why='IMAP connection setup installs only IMAP implementations.'),
    'pp_pop3': evidence('lib/pop3.c', 1436,
        why='POP3 connection setup installs only POP3 implementations.'),
    'pp_smtp': evidence('lib/smtp.c', 1685,
        why='SMTP connection setup installs only SMTP implementations.'),
    'wc_alloc': evidence('lib/transfer.c', 573, 579,
        'Wildcard state is internal and zero allocated.'),
    'wc_assignment': evidence('lib/ftp.c', 4003, 4004,
        'The sole non-null assignment to WildcardData.dtor is the FTP wildcard cleanup function.'),
    'wc_clear': evidence('lib/ftp.c', 4031, 4032,
        'Failure clears the callback; it does not install another target.'),
    'external_mime_assignment': evidence('lib/mime.c', 1479, 1498,
        'The public curl_mime_data_cb API accepts arbitrary application read/seek/free callbacks. These three dispatch families cannot have complete closed project-internal target sets.'),
}

SITES = []
def site(sid, family, file, caller, line, expression, targets, refs, guard, rationale, limitations):
    raw = (SRC / file).read_text().splitlines()[line-1]
    assert expression in raw, (sid, raw, expression)
    SITES.append({'id': sid, 'family': family, 'caller': f'{file}::{caller}',
        'caller_file': file, 'caller_function': caller,
        'callsite': {'line': line, 'column': raw.index(expression)+1,
                     'column_convention': '1-based start of the indirect callee expression in the original source',
                     'callee_expression': expression, 'snippet': raw.strip()},
        'expected_targets': targets, 'target_set_status': 'complete_for_this_site_under_stated_scope',
        'supporting_evidence': refs, 'execution_guard': guard,
        'rationale': rationale, 'limitations': limitations})

mime_limits = 'Opaque public MIME objects are used through supported APIs; memory corruption or direct writes to private struct fields are outside scope.'
site('mime-encode-read','mime_encoder','lib/mime.c','read_encoded_part_content',778,
    'part->encoder->encodefunc',
    [target('lib/mime.c', n, l) for n,l in [('encoder_nop_read',290),('encoder_7bit_read',317),('encoder_base64_read',342),('encoder_qp_read',463)]],
    ['mime_table','mime_assignment','mime_copy','mime_guard_read'],
    'part->encoder is non-null; buffered input is available or end of input has been reached.',
    'The encoder name selects one of five immutable table rows; binary and 8bit share encoder_nop_read.',mime_limits)
site('mime-encode-size','mime_encoder','lib/mime.c','mime_size',1640,
    'part->encoder->sizefunc',
    [target('lib/mime.c', n, l) for n,l in [('encoder_nop_size',311),('encoder_base64_size',426),('encoder_qp_size',564)]],
    ['mime_table','mime_assignment','mime_copy'],'part->encoder is non-null.',
    'The five immutable encoder rows contain exactly three distinct size callbacks.',mime_limits)

md5_refs = ['md5_params','md5_store','md5_call_pop3','md5_call_digest']
md5_limits = 'The private Curl_MD5_* entry points are reached through libcurl-internal calls. Arbitrary outside calls to private hidden symbols and forged contexts are excluded.'
for sid,caller,line,expr,kind in [
    ('md5-init','Curl_MD5_init',593,'(*md5params->md5_init_func)','init'),
    ('md5-update','Curl_MD5_update',605,'(*context->md5_hash->md5_update_func)','update'),
    ('md5-final','Curl_MD5_final',612,'(*context->md5_hash->md5_final_func)','final')]:
    site(sid,'md5_params','lib/md5.c',caller,line,expr,[MD5[kind]],md5_refs,
         'A successfully allocated, initialized MD5 context is supplied (init runs after both allocations).',
         'All lib/ callers of Curl_MD5_init pass &Curl_DIGEST_MD5; no other MD5_params object or write to the retained parameter field exists.',md5_limits)

hmac_refs = ['hmac_md5','hmac_sha256','hmac_cram','hmac_aws','hmac_scache','hmac_forward','hmac_store','hmac_final_alias','unused_sha512_params']
hmac_limits = 'Private Curl_HMAC_* entry points are restricted to libcurl-internal callers. This is three representative syntactic sites, not every HMAC call expression. HTTPSIG is disabled in this build; its source would only add an existing SHA256 source. The unused SHA512/256 HMAC object is not treated as an actual argument source.'
for sid,caller,line,expr,kind,guard in [
    ('hmac-init','Curl_HMAC_init',77,'hashparams->hinit','init','Context allocation succeeded; the first priming initialization is evaluated.'),
    ('hmac-update','Curl_HMAC_update',106,'ctxt->hash->hupdate','update','A successfully initialized HMAC context is supplied.'),
    ('hmac-final','Curl_HMAC_final',119,'hashparams->hfinal','final','A successfully initialized HMAC context is supplied; null output is redirected to internal scratch storage.')]:
    site(sid,'hmac_params','lib/hmac.c',caller,line,expr,[MD5[kind],SHA256[kind]],hmac_refs,guard,
         'All lib/ argument origins to Curl_HMAC_init/Curl_hmacit are Curl_HMAC_MD5 or Curl_HMAC_SHA256. The retained parameter pointer preserves that two-object bound.',hmac_limits)

pp_refs = ['pp_macro','pp_ftp','pp_imap','pp_pop3','pp_smtp']
pp_limits = 'This is a union across real FTP, IMAP, POP3 and SMTP connection objects at the generic pingpong site. A particular connection has exactly its own protocol pair. Other protocol handlers are not pingpong registrations and are not targets.'
site('pingpong-state','pingpong','lib/pingpong.c','Curl_pp_statemach',116,
    'pp->statemachine',
    [target(f'lib/{f}.c',n,l) for f,n,l in [('ftp','ftp_pp_statemachine',3190),('imap','imap_pp_statemachine',1563),('pop3','pop3_statemachine',1272),('smtp','smtp_pp_statemachine',1516)]],
    pp_refs,'The protocol has run its PINGPONG_SETUP and rc indicates socket readiness or buffered input.',
    'There are exactly four PINGPONG_SETUP invocations in lib/, and no other member assignments; all four protocols are enabled.',pp_limits)
site('pingpong-response','pingpong','lib/pingpong.c','Curl_pp_readresp',307,
    'pp->endofresp',
    [target(f'lib/{f}.c',n,l) for f,n,l in [('ftp','ftp_endofresp',585),('imap','imap_endofresp',299),('pop3','pop3_endofresp',292),('smtp','smtp_endofresp',494)]],
    pp_refs,'The protocol has run its PINGPONG_SETUP; a complete, valid response line has been received and Curl_client_write succeeded.',
    'Each enabled pingpong protocol registers exactly one end-of-response implementation in the same connection object.',pp_limits)
site('ftp-wildcard-dtor','wildcard_dtor','lib/ftplistparser.c','Curl_wildcard_dtor',197,
    'wc->dtor',[target('lib/ftp.c','wc_data_dtor',3943)],
    ['wc_alloc','wc_assignment','wc_clear'],'The wildcard object and its destructor member are non-null.',
    'The internal wildcard state begins zeroed; FTP wildcard initialization supplies the sole non-null destructor assignment, and cleanup/failure only clear it.',
    'This destructor is unrelated to caller-supplied FTP chunk/begin/end callbacks; those do not assign WildcardData.dtor.')

EXCLUDED = []
for sid,caller,line,expr in [
    ('mime-user-read','read_part_content',742,'part->readfunc'),
    ('mime-user-seek','mime_part_rewind',989,'part->seekfunc'),
    ('mime-user-free','cleanup_part_content',1040,'part->freefunc')]:
    raw = (SRC/'lib/mime.c').read_text().splitlines()[line-1]
    EXCLUDED.append({'id':sid,'caller':f'lib/mime.c::{caller}',
        'file':'lib/mime.c','line':line,'column':raw.index(expr)+1,'snippet':raw.strip(),
        'enumerated':False,'reason':'A public API can install arbitrary application callbacks. Some branches can also use internal helpers; that does not bound the whole site to project-internal targets.',
        'supporting_evidence':['external_mime_assignment']})

def preprocess_verification():
    db = json.loads((BUILD/'compile_commands.json').read_text())
    files = sorted({s['caller_file'] for s in SITES} |
                   {t['file'] for s in SITES for t in s['expected_targets']} |
                   {'lib/vauth/cram.c','lib/http_aws_sigv4.c','lib/vauth/digest.c','lib/vtls/vtls_scache.c'})
    (OUT/'preprocessed').mkdir(exist_ok=True)
    results=[]
    for file in files:
        entry = next(e for e in db if Path(e['file']).resolve() == (SRC/file).resolve())
        args = shlex.split(entry['command'])
        clean=[]; skip=False
        for arg in args:
            if skip:
                skip=False; continue
            if arg == '-o':
                skip=True; continue
            if arg == '-c':
                continue
            clean.append(arg)
        dest = OUT/'preprocessed'/file.replace('/','__').replace('.c','.i')
        clean.extend(['-E','-o',str(dest)])
        proc=subprocess.run(clean,cwd=entry['directory'],text=True,capture_output=True)
        assert proc.returncode == 0, (file,proc.stderr)
        active=set(); active_text={}; current_file=''; line=0
        for raw in dest.read_text().splitlines():
            m=re.match(r'#\s+(\d+)\s+"([^"]+)"',raw)
            if m:
                line=int(m.group(1)); current_file=m.group(2); continue
            if current_file == str(SRC/file):
                if raw.strip():
                    active.add(line); active_text[line]=raw
            line += 1
        checks=[]
        for s in SITES:
            if s['caller_file']==file:
                ln=s['callsite']['line']
                assert ln in active,(file,ln,'inactive callsite')
                checks.append({'kind':'callsite_active','site_id':s['id'],'line':ln,'preprocessed_text':active_text[ln]})
        for t in {t['id']:t for s in SITES for t in s['expected_targets'] if t['file']==file}.values():
            ln=t['definition_line']
            assert ln in active,(file,ln,'inactive target definition')
            assert t['function'] in active_text[ln],(t,active_text[ln])
            checks.append({'kind':'target_definition_active','target_id':t['id'],'line':ln,'preprocessed_text':active_text[ln]})
        results.append({'file':file,'returncode':proc.returncode,'preprocessed_file':str(dest.relative_to(OUT)),
                        'preprocessed_sha256':sha(dest),'checks':checks,'diagnostics':proc.stderr.strip()})
    return results

def main():
    verification=preprocess_verification()
    config=BUILD/'lib/curl_config.h'
    cache=BUILD/'CMakeCache.txt'
    config_text=config.read_text()
    enabled=['FTP','IMAP','POP3','SMTP','MIME','DIGEST_AUTH']
    for x in enabled:
        assert f'/* #undef CURL_DISABLE_{x} */' in config_text
    assert '#define USE_OPENSSL 1' in config_text
    assert '#define CURL_DISABLE_HTTPSIG 1' in config_text
    provenance_files=sorted({e['file'] for e in E.values()} | {s['caller_file'] for s in SITES} | {t['file'] for s in SITES for t in s['expected_targets']})
    commit=subprocess.check_output(['git','-C',str(SRC),'rev-parse','HEAD'],text=True).strip()
    audit={
        'schema_version':1,'title':'Curated internal indirect-call subset: real configured libcurl',
        'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'analyzer_blind_declaration':'Selected, read, justified and frozen without seeing either Yasa C or CodeGraph C predictions for this project.',
        'source':{'repository':'https://github.com/curl/curl','commit':commit,'root':str(SRC),
                  'source_sha256':{f:sha(SRC/f) for f in provenance_files}},
        'configured_build':{'compile_commands':str(BUILD/'compile_commands.json'),
                            'compile_commands_sha256':sha(BUILD/'compile_commands.json'),
                            'curl_config_h_sha256':sha(config),'cmake_cache_sha256':sha(cache),
                            'active_assumptions':['USE_OPENSSL=1','FTP enabled','IMAP enabled','POP3 enabled','SMTP enabled','MIME enabled','DIGEST_AUTH enabled','HTTPSIG disabled']},
        'scope':{
            'population':'11 manually selected syntactic indirect-call sites in libcurl, across five callback mechanisms.',
            'selection_basis':'Readable bounded internal target provenance, mechanism diversity and high confidence; no tool predictions were used to select sites.',
            'closed_world_boundary':'Supported libcurl API executions and libcurl-internal callers of private Curl_* routines; valid objects and no memory corruption. External caller-supplied callbacks are excluded from target enumeration.',
            'target_meaning':'The complete set of project-internal functions that can be called at this selected source expression over valid executions under this configuration.',
            'identity':'Repository-relative file::function; disambiguates static functions and aligns with file-aware build gold.',
            'not_claimed':['Overall project indirect-call recall','A representative random sample','A complete inventory of indirect calls','Proof of all runtime path feasibility beyond the documented registration and normal protocol use'],
            'metric_guidance':'Report recall only as curated-indirect-subset recall (11 sites / 25 site-target edges). If an analyzer emits only caller-to-callee edges, report that representation explicitly; these selected pairs are unique even after erasing site locations. Do not label missing target pairs false positives or extrapolate this subset to all callbacks.'},
        'counts':{'sites':len(SITES),'site_target_edges':sum(len(s['expected_targets']) for s in SITES),
                  'unique_caller_target_edges':len({(s['caller'],t['id']) for s in SITES for t in s['expected_targets']}),
                  'families':len({s['family'] for s in SITES}),'unique_target_functions':len({t['id'] for s in SITES for t in s['expected_targets']})},
        'sites':SITES,'evidence':E,'excluded_external_callback_inventory':EXCLUDED,
        'manual_cross_reference_checks':{
            'MD5_params':'rg over lib/ found only Curl_DIGEST_MD5 as an initializer. Curl_MD5_init arguments: pop3.c:574 and vauth/digest.c:405,419,442,460, all &Curl_DIGEST_MD5.',
            'HMAC_params':'lib/ argument sources: vauth/cram.c:60 is &Curl_HMAC_MD5; http_aws_sigv4.c:43 and vtls/vtls_scache.c:809,1165,1203 are &Curl_HMAC_SHA256; hmac.c:151 forwards its argument. http_httpsig.c:511 also uses SHA256 but is disabled. Curl_HMAC_SHA512_256 has only a declaration and definition in lib/, no use as an argument.',
            'mime_encoder':'Only non-null origin is encoders in curl_mime_encoder; mime.c:1214 copies an existing encoder. The object is internal; there is no callback registration API for its encodefunc or sizefunc.',
            'pingpong':'Only macro PINGPONG_SETUP assigns statemachine/endofresp; exactly four invocations exist in lib/: ftp.c:3540, imap.c:2289, pop3.c:1436, smtp.c:1685.',
            'wildcard':'WildcardData.dtor starts zeroed; ftp.c:4004 assigns wc_data_dtor, ftp.c:4031 and ftplistparser.c:198 clear it; no other non-null assignment found. Generic unrelated structs also named dtor were not merged.'},
        'compiler_preprocessing_verification':verification,
    }
    gold=OUT/'indirect-gold.json'
    gold.write_text(json.dumps(audit,indent=2)+'\n')
    checksum=sha(gold)
    (OUT/'indirect-gold.sha256').write_text(f'{checksum}  indirect-gold.json\n')
    (OUT/'freeze.json').write_text(json.dumps({'frozen_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'gold_file':'indirect-gold.json','sha256':checksum,'source_commit':commit,
        'analyzer_outputs_seen_before_freeze':False,'counts':audit['counts']},indent=2)+'\n')
    (OUT/'expected-edges.tsv').write_text('site_id\tcaller\tcallsite_line\tcallsite_column\ttarget\n'+''.join(
        f"{s['id']}\t{s['caller']}\t{s['callsite']['line']}\t{s['callsite']['column']}\t{t['id']}\n"
        for s in SITES for t in s['expected_targets']))
    print(json.dumps({'gold':str(gold),'sha256':checksum,'counts':audit['counts']},indent=2))

if __name__=='__main__':
    main()
