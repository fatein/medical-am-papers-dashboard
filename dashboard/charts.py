"""Plotly figures shared by the app and offline exports."""
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from .analytics import yearly_counts, composition
from .labels import COLORS, label


def style(fig,height=380):
    fig.update_layout(template='plotly_white',height=height,
                      margin=dict(l=18,r=18,t=26,b=48),
                      font=dict(family='Microsoft YaHei, Arial, sans-serif',size=12,color='#496078'),
                      paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',
                      hoverlabel=dict(bgcolor='white'),
                      legend=dict(orientation='h',y=-.22,x=0,font=dict(size=11)))
    fig.update_xaxes(showgrid=False,zeroline=False)
    fig.update_yaxes(gridcolor='#E6ECF1',zeroline=False)
    return fig


def annual_chart(frame,years):
    table=yearly_counts(frame,years)
    fig=make_subplots(specs=[[{'secondary_y':True}]])
    fig.add_trace(go.Bar(x=table.publication_year,y=table.n,name='年度论文',
                        marker_color='#137F75',marker_line_width=0,
                        hovertemplate='%{x} 年<br>%{y:,} 篇<extra>年度论文</extra>'))
    fig.add_trace(go.Scatter(x=table.publication_year,y=table.cumulative_n,name='范围内累计',
                            mode='lines+markers',line=dict(color='#5074BD',width=2.5),
                            marker=dict(size=5),hovertemplate='%{x} 年<br>累计 %{y:,} 篇<extra></extra>'),secondary_y=True)
    fig.update_yaxes(title_text='年度篇数',secondary_y=False,rangemode='tozero')
    fig.update_yaxes(title_text='范围内累计篇数',secondary_y=True,showgrid=False,rangemode='tozero')
    fig.update_xaxes(dtick=1,tickangle=-35,range=[years[0]-.5,years[1]+.5])
    fig.update_layout(hovermode='x unified',bargap=.3)
    return style(fig,385)


def distribution_chart(frame,column,mapping):
    counts=frame[column].value_counts().sort_values(ascending=True)
    fig=go.Figure(go.Bar(x=counts.values,y=[label(c,mapping) for c in counts.index],
                         orientation='h',marker_color='#5074BD',
                         text=counts.values,textposition='outside',cliponaxis=False,
                         hovertemplate='%{y}<br>%{x:,} 篇<extra></extra>'))
    fig.update_xaxes(title_text='论文篇数',range=[0,max(counts.max()*1.25,1)] if len(counts) else [0,1])
    fig.update_yaxes(showgrid=False)
    return style(fig,385)


def composition_chart(frame,column,mapping,years,percent=True):
    table=composition(frame,column,years,percent)
    fig=go.Figure()
    for i,code in enumerate(sorted(table.columns,key=lambda x:list(mapping).index(x) if x in mapping else 99)):
        fig.add_trace(go.Bar(x=table.index,y=table[code],name=label(code,mapping),
                            marker_color=COLORS[i%len(COLORS)],
                            hovertemplate='%{x} 年<br>%{y:.1f}'+('%' if percent else ' 篇')+'<extra>%{fullData.name}</extra>'))
    fig.update_layout(barmode='stack',bargap=.22,hovermode='x unified')
    fig.update_xaxes(dtick=1,tickangle=-35)
    fig.update_yaxes(title_text='年度论文占比（%）' if percent else '年度论文数量',
                     range=[0,100] if percent else None)
    return style(fig,480 if len(table.columns)>9 else 430)


def comparison_chart(table,mapping):
    d=table.sort_values('delta_pp')
    fig=go.Figure(go.Bar(x=d.delta_pp,y=[label(c,mapping) for c in d.code],orientation='h',
                         marker_color=['#137F75' if n>=0 else '#CF785F' for n in d.delta_pp],
                         customdata=d[['early_n','late_n','early_pct','late_pct']].to_numpy(),
                         hovertemplate='%{y}<br>变化 %{x:+.2f} 个百分点<br>前期 %{customdata[0]} 篇 / %{customdata[2]:.1f}%<br>后期 %{customdata[1]} 篇 / %{customdata[3]:.1f}%<extra></extra>'))
    fig.update_xaxes(title_text='后期占比 − 前期占比（百分点）',zeroline=True,zerolinecolor='#8493A1')
    fig.update_yaxes(showgrid=False)
    return style(fig,max(320,len(d)*28+100))


def heatmap_chart(table,row_mapping,column_mapping):
    fig=go.Figure(go.Heatmap(z=table.to_numpy(),x=[label(x,column_mapping) for x in table.columns],
                             y=[label(y,row_mapping) for y in table.index],
                             colorscale=[[0,'#F0F5F7'],[.4,'#77B9AE'],[1,'#137F75']],
                             text=table.to_numpy(),texttemplate='%{text}',
                             hovertemplate='%{y}<br>%{x}<br>%{z} 篇<extra></extra>',
                             colorbar=dict(title='篇数',thickness=12)))
    fig.update_xaxes(tickangle=-30)
    return style(fig,max(400,len(table)*30+170))
