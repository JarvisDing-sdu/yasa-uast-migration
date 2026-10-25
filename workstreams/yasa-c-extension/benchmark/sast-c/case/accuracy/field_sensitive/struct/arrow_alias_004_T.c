/*
 * evaluation information start
 * real case = true
 * evaluation item = 结构体字段
 * scene introduction = 通过指针写入、通过变量读取
 * bind_url = accuracy/field_sensitive/struct/arrow_alias_004_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
struct Pair { char *data; char *safe; struct { char *v; } inner; };

void arrow_alias_004_T(void) {
    struct Pair p;
    struct Pair *q = &p;
    q->data = taint_src();
    taint_sink(p.data);
}
