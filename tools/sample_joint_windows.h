static int screen_lower, screen_sampled;
static char screen_sample[2048];

static void screen_observe(ReplayQuery *q, ReplaySignal *signals, const int obj[2], int open,
                           unsigned ops, const P9JointResult *result)
{
    if (q->checks%127!=1 || screen_sampled>=96) return;
    PexaMan_t *p=q->p;
    int used=snprintf(screen_sample,sizeof(screen_sample),"WINDOW %u %d %d %d %d %d %d %u %u %u",
                      q->target,p->nNodes,screen_lower,q->bound,obj[0],obj[1],open,ops,
                      result->supported[0],result->supported[1]);
    for (int j=0;j<p->nObjs-1;++j) {
        unsigned pending=0;
        if (j>=p->nVars) for (int a=1;a<=q->rows/2;++a) {
            int v=replay_count_var(p,j,q->rows,a);
            if (sat_solver_get_var_value(p->pSat,v)==l_Undef) pending|=1u<<a;
        }
        used+=snprintf(screen_sample+used,sizeof(screen_sample)-used," %u,%u,%u,%u",
                       signals[j].zeros,signals[j].ones,signals[j].domain,pending);
    }
}
