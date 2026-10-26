/*
 * evaluation information start
 * real case = true
 * evaluation item = 编译单元
 * scene introduction = 各编译单元使用自己包含的 static inline 函数
 * bind_url = c_semantics/linkage/header_static_name_collision_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
#include "a.h"
void header_static_name_collision_T(void) { taint_sink(helper()); }
