/*
 * evaluation information start
 * real case = false
 * evaluation item = 宏时序
 * scene introduction = 真实 API
 * bind_url = c_semantics/real/real_macro_redefine_to_safe_F
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#define INPUT() getenv("YASA_QUALITY")
#undef INPUT
#define INPUT() "safe"
void real_macro_redefine_to_safe_F(void) { system(INPUT()); }
