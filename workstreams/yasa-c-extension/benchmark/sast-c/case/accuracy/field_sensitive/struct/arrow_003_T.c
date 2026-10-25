/*
 * evaluation information start
 * real case = true
 * evaluation item = 结构体字段
 * scene introduction = 箭头运算符字段
 * bind_url = accuracy/field_sensitive/struct/arrow_003_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
struct Pair { char *data; char *safe; struct { char *v; } inner; };

void arrow_003_T(struct Pair *p) {
    p->data = taint_src();
    taint_sink(p->data);
}
