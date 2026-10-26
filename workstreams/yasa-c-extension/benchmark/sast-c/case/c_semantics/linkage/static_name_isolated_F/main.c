/*
 * evaluation information start
 * real case = false
 * evaluation item = 编译单元
 * scene introduction = 另一文件中同名 static 函数不可见
 * bind_url = c_semantics/linkage/static_name_isolated_F
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
static char *helper2(void) { return "safe"; }
void static_name_isolated_F(void) { taint_sink(helper2()); }
