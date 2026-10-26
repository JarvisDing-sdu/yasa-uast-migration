/*
 * evaluation information start
 * real case = true
 * evaluation item = 多级指针
 * scene introduction = 真实 API：二级间接写回
 * bind_url = c_semantics/real/real_double_indirection_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

void real_double_indirection_T(void) {
    char *p = "safe";
    char **q = &p;
    char ***r = &q;
    **r = getenv("YASA_QUALITY");
    system(p);
}
