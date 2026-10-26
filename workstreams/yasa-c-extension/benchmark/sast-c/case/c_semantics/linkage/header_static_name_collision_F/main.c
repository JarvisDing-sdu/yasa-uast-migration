/*
 * evaluation information start
 * real case = false
 * evaluation item = 编译单元
 * scene introduction = 另一编译单元的污点 static inline 不可见
 * bind_url = c_semantics/linkage/header_static_name_collision_F
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
#include "z.h"
void header_static_name_collision_F(void) { taint_sink(helper()); }
