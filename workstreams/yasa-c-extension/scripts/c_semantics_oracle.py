#!/usr/bin/env python3
"""用 clang 实际编译运行 c_semantics 回归用例，核对 T/F 标签。

source（taint_src / getenv）返回含 "INPUT" 标记的字符串，sink（taint_sink / system）
检查实参内容是否含该标记。带 int 参数的用例分别以 0、1 调用，任一次命中即为 T。
sink 为长度或格式串的数值用例无法用内容判定，标记为 skip（按 C 语义：输入决定长度/位置参数）。

用法: python3 c_semantics_oracle.py   退出码 0 = 全部一致
"""
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES = os.path.join(ROOT, 'benchmark', 'sast-c', 'case', 'c_semantics')
META = os.path.join(ROOT, 'benchmark', 'c_semantics_cases.json')
CC = os.environ.get('CC', 'clang')
SKIP = {
    'real/numeric_length_taint_T': 'sink 是 memcpy 长度，运行时无法按内容判定',
    'real/numeric_format_index_T': 'sink 是 printf 的格式串（输入选择位置参数），运行时无法按内容判定',
}

STUB = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int hit;
char *taint_src(void) { return strdup("TAINTED_INPUT"); }
char *oracle_getenv(const char *n) { (void)n; return strdup("TAINTED_INPUT"); }
static void check(const char *s) { if (s && strstr(s, "INPUT")) hit = 1; }
void taint_sink(const char *s) { check(s); }
int oracle_system(const char *s) { check(s); return 0; }
int oracle_hit(void) { int h = hit; hit = 0; return h; }
'''


def run_case(path, flags):
    full = os.path.join(CASES, path)
    if os.path.isdir(full):
        srcs = [os.path.join(full, f) for f in sorted(os.listdir(full)) if f.endswith('.c')]
        main = os.path.join(full, 'main.c')
    else:
        srcs, main = [full + '.c'], full + '.c'
    name = os.path.basename(path)
    sig = re.search(r'\b' + re.escape(name) + r'\s*\(([^)]*)\)', open(main).read()).group(1).strip()
    takes_int = sig not in ('', 'void')
    calls = f'{name}(0); r |= oracle_hit(); {name}(1); r |= oracle_hit();' if takes_int else f'{name}(); r |= oracle_hit();'
    proto = f'void {name}({"int" if takes_int else "void"});'
    driver = f'{proto}\nint oracle_hit(void);\n#include <stdio.h>\nint main(void) {{ int r = 0; {calls} puts(r ? "TAINT" : "SAFE"); return 0; }}\n'
    with tempfile.TemporaryDirectory() as tmp:
        open(os.path.join(tmp, 'stub.c'), 'w').write(STUB)
        open(os.path.join(tmp, 'driver.c'), 'w').write(driver)
        exe = os.path.join(tmp, 'a.out')
        stub_o = os.path.join(tmp, 'stub.o')
        # stub 不带重命名宏，单独编译
        subprocess.run([CC, '-w', '-c', '-o', stub_o, os.path.join(tmp, 'stub.c')], check=True)
        renames = ['-Dgetenv=oracle_getenv', '-Dsystem=oracle_system']
        r = subprocess.run([CC, '-w', '-O0', '-o', exe, *renames, *flags, *srcs, os.path.join(tmp, 'driver.c'), stub_o],
                           capture_output=True, text=True)
        if r.returncode != 0:
            return 'COMPILE_ERROR: ' + r.stderr.strip().splitlines()[0]
        out = subprocess.run([exe], capture_output=True, text=True, timeout=10).stdout.strip()
        return out


def main():
    meta = json.load(open(META))
    bad = 0
    for c in meta:
        if c['path'] in SKIP:
            print(f"skip   {c['path']}: {SKIP[c['path']]}")
            continue
        got = run_case(c['path'], c.get('oracle_flags', []))
        want = 'TAINT' if c['expected'] else 'SAFE'
        ok = got == want
        bad += not ok
        print(f"{'ok  ' if ok else 'FAIL'}   {c['path']}  expected={want} oracle={got} flags={' '.join(c.get('oracle_flags', []))}")
    print(f'\n{len(meta) - bad - len(SKIP)}/{len(meta) - len(SKIP)} labels confirmed, {len(SKIP)} skipped')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
