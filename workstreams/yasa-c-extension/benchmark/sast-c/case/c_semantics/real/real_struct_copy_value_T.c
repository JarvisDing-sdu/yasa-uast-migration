/*
 * evaluation information start
 * real case = true
 * evaluation item = 结构体值复制
 * scene introduction = 真实 API
 * bind_url = c_semantics/real/real_struct_copy_value_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
struct S { char *p; };

void real_struct_copy_value_T(void) {
    struct S a = { getenv("YASA_QUALITY") };
    struct S b = a;
    a.p = "safe";
    system(b.p);
}
