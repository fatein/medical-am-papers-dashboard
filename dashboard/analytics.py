"""Document-level statistics, with explicit time windows and denominators."""
import pandas as pd


def yearly_counts(frame, year_range):
    index=pd.Index(range(year_range[0],year_range[1]+1),name='publication_year')
    counts=frame.groupby('publication_year').size().reindex(index,fill_value=0)
    result=counts.rename('n').to_frame()
    result['cumulative_n']=counts.cumsum()
    previous=counts.shift(1)
    result['yoy_pct']=(counts/previous.where(previous.ne(0))-1)*100
    # Supplement years remain incomplete until the project explicitly closes them.
    result.loc[result.index >= 2026, 'yoy_pct'] = float('nan')
    return result.reset_index()


def composition(frame, column, year_range, percent=False):
    if frame.empty: return pd.DataFrame()
    table=pd.crosstab(frame.publication_year,frame[column])
    table=table.reindex(range(year_range[0],year_range[1]+1),fill_value=0)
    if percent:
        table=table.div(table.sum(axis=1).replace(0,float('nan')),axis=0).fillna(0)*100
    return table


def period_comparison(frame, column, early, late):
    if early[1]>=late[0]: raise ValueError('比较区间不能重叠，较早区间必须在前。')
    a=frame.loc[frame.publication_year.between(*early)]
    b=frame.loc[frame.publication_year.between(*late)]
    codes=sorted(set(a[column])|set(b[column]))
    result=pd.DataFrame({'code':codes})
    result['early_n']=result.code.map(a[column].value_counts()).fillna(0).astype(int)
    result['late_n']=result.code.map(b[column].value_counts()).fillna(0).astype(int)
    result['early_total']=len(a)
    result['late_total']=len(b)
    result['early_pct']=result.early_n/len(a)*100 if len(a) else float('nan')
    result['late_pct']=result.late_n/len(b)*100 if len(b) else float('nan')
    result['delta_pp']=result.late_pct-result.early_pct
    return result.sort_values('delta_pp',ascending=False)


def cross_counts(frame, row, column):
    if frame.empty: return pd.DataFrame()
    return pd.crosstab(frame[row],frame[column])
