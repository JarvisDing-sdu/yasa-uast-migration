/*
 * evaluation information start
 * real case = true
 * evaluation item = 跨文件
 * scene introduction = 全局变量在一个文件写入、另一个文件通过 extern 读取
 * bind_url = completeness/cross_file/extern_global_004_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
char *shared_value;
void read_shared(void);
void extern_global_004_T(void) {
    shared_value = taint_src();
    read_shared();
}
