/*
 * evaluation information start
 * real case = true
 * evaluation item = 指针成员复制
 * scene introduction = 复制结构体后两个指针字段指向同一缓冲区
 * bind_url = c_semantics/aggregate/struct_pointer_member_shares_pointee_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
struct S { char *p; };

void struct_pointer_member_shares_pointee_T(void) {
    char buf[64] = "safe";
    struct S a = { buf };
    struct S b = a;
    strcpy(a.p, taint_src());
    taint_sink(b.p);
}
