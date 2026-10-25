/*
 * evaluation information start
 * real case = true
 * evaluation item = 结构体字段
 * scene introduction = 结构体指针作为参数传递
 * bind_url = accuracy/field_sensitive/struct/struct_param_009_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
struct Pair { char *data; char *safe; struct { char *v; } inner; };

static void use(struct Pair *p) {
    taint_sink(p->data);
}
void struct_param_009_T(void) {
    struct Pair p;
    p.data = taint_src();
    use(&p);
}
