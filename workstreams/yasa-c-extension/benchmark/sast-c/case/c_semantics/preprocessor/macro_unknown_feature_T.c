/*
 * evaluation information start
 * real case = true
 * evaluation item = 条件环境
 * scene introduction = 未指定的特性宏：覆盖两个配置（FEATURE 定义时有污点）
 * bind_url = c_semantics/preprocessor/macro_unknown_feature_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
#ifdef FEATURE
#define INPUT() taint_src()
#else
#define INPUT() "safe"
#endif
void macro_unknown_feature_T(void) { taint_sink(INPUT()); }
