/*
 * evaluation information start
 * real case = true
 * evaluation item = 联合体
 * scene introduction = 写一个成员、读另一个成员
 * bind_url = accuracy/field_sensitive/struct/union_010_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
typedef union { char *first; char *second; } Both;
void union_010_T(void) {
    Both u;
    u.first = taint_src();
    taint_sink(u.second);
}
