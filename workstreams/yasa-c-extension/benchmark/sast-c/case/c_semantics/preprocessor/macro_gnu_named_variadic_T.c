/*
 * evaluation information start
 * real case = false
 * evaluation item = 宏替换
 * scene introduction = GNU 具名变参 args...：收集其余全部实参
 * bind_url = c_semantics/preprocessor/macro_gnu_named_variadic_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
#define FORMAT(buf, fmt, args...) sprintf(buf, fmt, args)
void macro_gnu_named_variadic_T(void) {
    char cmd[256];
    FORMAT(cmd, "%s %s", "echo", taint_src());
    taint_sink(cmd);
}
