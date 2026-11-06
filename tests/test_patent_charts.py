from pathlib import Path

import pandas as pd
import pytest

from dashboard import patent_charts
from dashboard.patent_data import filter_patents, load_patents


def sample_publications():
    return pd.DataFrame([
        {'publication_id': 'CN1A', 'publication_year': 2021, 'country': 'CN',
         'medical_categories': ['dental', 'dental', 'implants_and_prostheses'],
         'applicants': ['北京医疗技术有限公司', 'Alpha GmbH', 'Alpha GmbH']},
        {'publication_id': 'US2A', 'publication_year': 2023, 'country': 'US',
         'medical_categories': ['dental'], 'applicants': ['Alpha GmbH']},
        {'publication_id': 'EP3A', 'publication_year': None, 'country': 'EP',
         'medical_categories': ['implants_and_prostheses'], 'applicants': []},
    ])


def test_counts_use_publications_and_deduplicate_multilabel_memberships():
    frame = sample_publications()
    # A repeated input publication must not inflate any chart.
    frame = pd.concat([frame, frame.iloc[:1]], ignore_index=True)
    counts = patent_charts.patent_counts(frame)
    assert counts['years'].to_dict() == {'2021': 1, '2023': 1, 'unknown': 1}
    assert counts['applications'].to_dict() == {'dental': 2, 'implants_and_prostheses': 2}
    assert counts['applicants'].to_dict() == {'Alpha GmbH': 2, '北京医疗技术有限公司': 1}
    assert counts['authorities'].to_dict() == {'CN': 1, 'EP': 1, 'US': 1}


@pytest.mark.parametrize('locale', ['zh', 'en', 'de'])
def test_figures_keep_original_applicants_and_localize_all_chart_labels(locale):
    figures = patent_charts.patent_figures(sample_publications(), locale)
    assert set(figures) == {'years', 'applications', 'applicants', 'authorities'}
    assert list(figures['years'].data[0].y) == [1, 1, 1]
    assert list(figures['applicants'].data[0].customdata) == ['Alpha GmbH', '北京医疗技术有限公司']
    assert list(figures['applicants'].data[0].x) == [2, 1]
    assert 'unknown' not in figures['years'].data[0].x
    expected_axis = {'zh': '公开记录数', 'en': 'Publications', 'de': 'Veröffentlichungen'}[locale]
    assert figures['applicants'].layout.xaxis.title.text == expected_axis
    assert figures['years'].layout.yaxis.title.text == expected_axis


def test_rankings_limit_to_ten_and_keep_full_long_names_in_hover():
    names = ['Original ' + ('medical devices ' * 8) + str(i) for i in range(12)]
    frame = sample_publications().iloc[:1].copy()
    frame.at[0, 'applicants'] = names
    figure = patent_charts.patent_figures(frame, 'de')['applicants']
    assert len(figure.data[0].x) == 10
    assert list(figure.data[0].customdata) == sorted(names)[:10]
    assert any('<br>' in label for label in figure.layout.yaxis.ticktext)
    assert all(len(label.split('<br>')) <= 2 for label in figure.layout.yaxis.ticktext)


def test_empty_results_create_four_empty_charts_without_false_counts():
    frame = sample_publications().iloc[:0]
    assert all(series.empty for series in patent_charts.patent_counts(frame).values())
    figures = patent_charts.patent_figures(frame, 'en')
    assert len(figures) == 4
    for figure in figures.values():
        assert not figure.data
        assert figure.layout.annotations[0].text == 'No matching publications'


def test_real_snapshot_and_filtered_year_totals_match_visible_records():
    source = load_patents(Path(__file__).resolve().parents[1])
    assert len(source) == 5516
    for frame in [source, filter_patents(source, applications=['dental'], years=(2020, 2024))]:
        counts = patent_charts.patent_counts(frame)
        assert counts['years'].sum() == len(frame)
        assert counts['authorities'].sum() == len(frame)
        expected_dental = sum('dental' in labels for labels in frame.medical_categories)
        assert counts['applications'].get('dental', 0) == expected_dental
        applicant = frame.iloc[0].applicants[0]
        expected_applicant = sum(applicant in names for names in frame.applicants)
        assert counts['applicants'][applicant] == expected_applicant
