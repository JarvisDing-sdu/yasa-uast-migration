/*
 * evaluation information start
 * real case = true
 * evaluation item = 结构体字段
 * scene introduction = typedef 匿名结构体
 * bind_url = accuracy/field_sensitive/struct/typedef_008_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
typedef struct { char *data; } Box;
void typedef_008_T(void) {
    Box b;
    b.data = taint_src();
    taint_sink(b.data);
}
