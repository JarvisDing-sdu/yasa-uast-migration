/*
 * evaluation information start
 * real case = true
 * evaluation item = 条件定义
 * scene introduction = 真实 API
 * bind_url = c_semantics/real/real_conditional_duplicate_function_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#ifdef FEATURE
char *pick_real(void) { return "safe"; }
#else
char *pick_real(void) { return getenv("YASA_QUALITY"); }
#endif
void real_conditional_duplicate_function_T(void) { system(pick_real()); }
