/*
 * evaluation information start
 * real case = false
 * evaluation item = 编译期常量
 * scene introduction = sizeof 污点缓冲区不是污点
 * bind_url = completeness/expression/sizeof_009_F
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
void sink_len(unsigned long n);
void sizeof_009_F(void) {
    char *t = taint_src();
    char buf[16];
    taint_sink((const char *)sizeof(t));
}
