char *taint_src(void);
static char *helper2(void) { return taint_src(); }
void other_unit2(void) { helper2(); }
