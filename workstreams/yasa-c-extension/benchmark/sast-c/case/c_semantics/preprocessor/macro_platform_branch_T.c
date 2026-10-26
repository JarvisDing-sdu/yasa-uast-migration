/*
 * evaluation information start
 * real case = true
 * evaluation item = 条件环境
 * scene introduction = 默认目标（非 Windows）选择 #else 分支
 * bind_url = c_semantics/preprocessor/macro_platform_branch_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
#ifdef _WIN32
#define INPUT() "safe"
#else
#define INPUT() taint_src()
#endif
void macro_platform_branch_T(void) { taint_sink(INPUT()); }
