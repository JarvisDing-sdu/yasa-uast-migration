/*
 * evaluation information start
 * real case = true
 * evaluation item = 短路求值
 * scene introduction = 未知条件 && expr 可能执行右侧
 * bind_url = c_semantics/control/short_circuit_unknown_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
void short_circuit_unknown_T(int c) {
    char *p = "safe";
    c && (p = taint_src());
    taint_sink(p);
}
