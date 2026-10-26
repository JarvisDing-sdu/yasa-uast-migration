/*
 * evaluation information start
 * real case = false
 * evaluation item = 条件环境
 * scene introduction = 默认目标（非 Windows）不使用 Windows 分支
 * bind_url = c_semantics/preprocessor/macro_platform_branch_F
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
#ifdef _WIN32
#define INPUT() taint_src()
#else
#define INPUT() "safe"
#endif
void macro_platform_branch_F(void) { taint_sink(INPUT()); }
