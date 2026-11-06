"""Filter-responsive publication analytics for the patent explorer."""
from __future__ import annotations

from collections import Counter
from html import escape
from textwrap import wrap

import pandas as pd
import plotly.graph_objects as go


APPLICATION_LABELS = {
    'dental': ('口腔与牙科', 'Dental', 'Zahnmedizin'),
    'implants_and_prostheses': ('植入物与假体', 'Implants and prostheses', 'Implantate und Prothesen'),
    'tissue_engineering_and_bioprinting': ('组织工程与生物打印', 'Tissue engineering and bioprinting', 'Gewebeengineering und Bioprinting'),
    'pharmaceuticals_and_drug_delivery': ('药物与递送', 'Pharmaceuticals and drug delivery', 'Arzneimittel und Wirkstofffreisetzung'),
    'surgical_tools_and_anatomical_models': ('手术工具与解剖模型', 'Surgical tools and anatomical models', 'Chirurgische Instrumente und anatomische Modelle'),
    'medical_devices_and_rehabilitation': ('医疗器械与康复', 'Medical devices and rehabilitation', 'Medizinprodukte und Rehabilitation'),
}
_COPY = {
    'years': ('公开年份趋势', 'Publications by year', 'Veröffentlichungen nach Jahr'),
    'applications': ('医疗应用分布', 'Medical applications', 'Medizinische Anwendungen'),
    'applicants': ('申请人 · 前 10', 'Applicants · Top 10', 'Anmelder · Top 10'),
    'authorities': ('公开国家／地区 · 前 10', 'Publication authorities · Top 10', 'Veröffentlichungsbehörden · Top 10'),
    'count': ('公开记录数', 'Publications', 'Veröffentlichungen'),
    'year': ('公开年份', 'Publication year', 'Veröffentlichungsjahr'),
    'unknown': ('年份未知', 'Unknown year', 'Unbekanntes Jahr'),
    'empty': ('没有匹配公开记录', 'No matching publications', 'Keine passenden Veröffentlichungen'),
}


def patent_counts(frame):
    """Count publications, counting each label/name once per publication.

    Years are publication years. Multi-label application and applicant totals
    may exceed the number of publications. Original applicant names stay exact.
    """
    unique = frame.drop_duplicates('publication_id')
    years = Counter('unknown' if pd.isna(year) else str(int(year))
                    for year in unique.publication_year)
    ordered_years = sorted((year for year in years if year != 'unknown'), key=int)
    if 'unknown' in years:
        ordered_years.append('unknown')
    result = {'years': pd.Series({year: years[year] for year in ordered_years}, dtype='int64')}
    for key, column in [('applications', 'medical_categories'), ('applicants', 'applicants'),
                        ('authorities', 'country')]:
        if key == 'authorities':
            counts = Counter(unique[column])
        else:
            memberships = {(row.publication_id, value)
                           for row in frame.itertuples() for value in getattr(row, column)}
            counts = Counter(value for _, value in memberships)
        result[key] = pd.Series(dict(sorted(counts.items(), key=lambda item: (-item[1], item[0]))),
                                dtype='int64')
    return result


def _style(figure, title):
    figure.update_layout(
        title=dict(text=title, x=0, font=dict(size=16)),
        template='plotly_white', height=440, showlegend=False,
        margin=dict(l=18, r=28, t=56, b=56),
        font=dict(family='Microsoft YaHei, Arial, sans-serif', size=11, color='#496078'),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        hoverlabel=dict(bgcolor='white'),
    )
    figure.update_xaxes(zeroline=False)
    figure.update_yaxes(zeroline=False)
    return figure


def _wrapped_label(value):
    lines = wrap(value, width=24, break_long_words=True)
    if len(lines) > 2:
        lines = [lines[0], lines[1].rstrip() + '…']
    return '<br>'.join(escape(part) for part in lines)


def patent_figures(frame, locale='zh'):
    """Build four independent, localized charts from the current filtered rows."""
    index = {'zh': 0, 'en': 1, 'de': 2}.get(locale, 0)
    copy = {key: labels[index] for key, labels in _COPY.items()}
    counts = patent_counts(frame)
    figures = {}
    for key, series in counts.items():
        figure = _style(go.Figure(), copy[key])
        if series.empty:
            figure.add_annotation(text=copy['empty'], x=.5, y=.5, xref='paper', yref='paper',
                                  showarrow=False)
            figure.update_xaxes(visible=False)
            figure.update_yaxes(visible=False)
        elif key == 'years':
            labels = [copy['unknown'] if year == 'unknown' else year for year in series.index]
            figure.add_bar(x=labels, y=series.tolist(), marker_color='#137F75',
                           hovertemplate='%{x}<br>%{y:,} ' + copy['count'] + '<extra></extra>')
            figure.update_xaxes(title_text=copy['year'], type='category', showgrid=False,
                                nticks=12, tickangle=-35)
            figure.update_yaxes(title_text=copy['count'], rangemode='tozero', gridcolor='#E6ECF1')
        else:
            if key in ('applicants', 'authorities'):
                series = series.head(10)
            labels = ([APPLICATION_LABELS[code][index] for code in series.index]
                      if key == 'applications' else series.index.tolist())
            positions = list(range(len(labels)))
            figure.add_bar(x=series.tolist(), y=positions, orientation='h',
                           customdata=labels, marker_color='#5074BD' if key == 'applicants' else '#137F75',
                           text=series.tolist(), textposition='outside', cliponaxis=False,
                           hovertemplate='%{customdata}<br>%{x:,} ' + copy['count'] + '<extra></extra>')
            figure.update_xaxes(title_text=copy['count'], range=[0, max(series.max()*1.2, 1)],
                                gridcolor='#E6ECF1')
            figure.update_yaxes(tickmode='array', tickvals=positions,
                                ticktext=[_wrapped_label(label) for label in labels],
                                autorange='reversed', showgrid=False, automargin=True)
        figures[key] = figure
    return figures
