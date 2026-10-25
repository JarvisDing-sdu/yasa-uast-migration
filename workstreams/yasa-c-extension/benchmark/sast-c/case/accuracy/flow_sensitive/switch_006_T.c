/*
 * evaluation information start
 * real case = true
 * evaluation item = 控制流
 * scene introduction = switch case
 * bind_url = accuracy/flow_sensitive/switch_006_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
void switch_006_T(int n) {
    char *t = taint_src();
    switch (n) {
    case 1:
        taint_sink(t);
        break;
    default:
        break;
    }
}
