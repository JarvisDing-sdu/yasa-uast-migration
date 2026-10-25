/*
 * evaluation information start
 * real case = false
 * evaluation item = 结构体字段
 * scene introduction = 区分不同字段
 * bind_url = accuracy/field_sensitive/struct/field_002_F
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
struct Pair { char *data; char *safe; struct { char *v; } inner; };

void field_002_F(void) {
    struct Pair p;
    p.data = taint_src();
    p.safe = "safe";
    taint_sink(p.safe);
}
