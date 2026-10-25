/*
 * evaluation information start
 * real case = true
 * evaluation item = 结构体字段
 * scene introduction = 嵌套结构体字段
 * bind_url = accuracy/field_sensitive/struct/nested_007_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
struct Pair { char *data; char *safe; struct { char *v; } inner; };

void nested_007_T(void) {
    struct Pair p;
    p.inner.v = taint_src();
    taint_sink(p.inner.v);
}
