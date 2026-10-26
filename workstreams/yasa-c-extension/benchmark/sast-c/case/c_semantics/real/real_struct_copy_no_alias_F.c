/*
 * evaluation information start
 * real case = false
 * evaluation item = 结构体值复制
 * scene introduction = 真实 API
 * bind_url = c_semantics/real/real_struct_copy_no_alias_F
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
struct S { char *p; };

void real_struct_copy_no_alias_F(void) {
    struct S a = { "safe" };
    struct S b = a;
    a.p = getenv("YASA_QUALITY");
    system(b.p);
}
