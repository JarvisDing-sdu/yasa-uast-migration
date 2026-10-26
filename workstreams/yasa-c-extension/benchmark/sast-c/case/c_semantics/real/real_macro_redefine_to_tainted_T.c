/*
 * evaluation information start
 * real case = true
 * evaluation item = 宏时序
 * scene introduction = 真实 API
 * bind_url = c_semantics/real/real_macro_redefine_to_tainted_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#define INPUT() "safe"
#undef INPUT
#define INPUT() getenv("YASA_QUALITY")
void real_macro_redefine_to_tainted_T(void) { system(INPUT()); }
