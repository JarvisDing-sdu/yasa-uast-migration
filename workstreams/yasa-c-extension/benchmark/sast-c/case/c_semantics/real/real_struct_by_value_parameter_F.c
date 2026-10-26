/*
 * evaluation information start
 * real case = false
 * evaluation item = 按值传参
 * scene introduction = 真实 API
 * bind_url = c_semantics/real/real_struct_by_value_parameter_F
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
struct S { char *p; };

static void mutate(struct S s) { s.p = getenv("YASA_QUALITY"); }
void real_struct_by_value_parameter_F(void) {
    struct S s = { "safe" };
    mutate(s);
    system(s.p);
}
