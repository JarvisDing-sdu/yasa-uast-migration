/*
 * evaluation information start
 * real case = false
 * evaluation item = 短路求值
 * scene introduction = 1 || expr 不执行右侧
 * bind_url = c_semantics/control/short_circuit_or_F
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
void short_circuit_or_F(void) {
    char *p = "safe";
    1 || (p = taint_src());
    taint_sink(p);
}
