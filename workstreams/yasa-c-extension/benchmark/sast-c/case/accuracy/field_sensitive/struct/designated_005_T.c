/*
 * evaluation information start
 * real case = true
 * evaluation item = 结构体字段
 * scene introduction = 指定初始化器
 * bind_url = accuracy/field_sensitive/struct/designated_005_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
struct Pair { char *data; char *safe; struct { char *v; } inner; };

void designated_005_T(void) {
    struct Pair p = { .data = taint_src(), .safe = "safe" };
    taint_sink(p.data);
}
