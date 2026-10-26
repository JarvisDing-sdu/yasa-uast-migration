/*
 * evaluation information start
 * real case = true
 * evaluation item = 短路求值
 * scene introduction = 1 && expr 执行右侧
 * bind_url = c_semantics/control/short_circuit_and_live_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
void short_circuit_and_live_T(void) {
    char *p = "safe";
    1 && (p = taint_src());
    taint_sink(p);
}
