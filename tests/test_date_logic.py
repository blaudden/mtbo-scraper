import pytest
from unittest.mock import patch
from click.testing import CliRunner
from datetime import datetime, timedelta
from src.main import main

@patch('src.main.EventorSource')
@patch('src.main.Storage')
def test_default_end_date(mock_storage, mock_source):
    runner = CliRunner()
    start = "2024-01-01"
    # Run main
    result = runner.invoke(main, ['--start-date', start])
    assert result.exit_code == 0
    
    # Check what fetch_event_list was called with
    # We need to get the instance created. 
    # Since EventorSource is instantiated multiple times (once per country),
    # we check if ANY call matched.
    instance = mock_source.return_value
    
    # Expected end date: 2024-01-01 + 456 days
    expected_end = (datetime(2024, 1, 1) + timedelta(days=456)).strftime('%Y-%m-%d')
    
    # Verify fetch_event_list called with correct dates
    # It's called for each source, so we check the arguments of the call
    instance.fetch_event_list.assert_called_with(start, expected_end)

@patch('src.main.EventorSource')
@patch('src.main.Storage')
def test_explicit_valid_date(mock_storage, mock_source):
    runner = CliRunner()
    start = "2024-01-01"
    end = "2024-02-01"
    result = runner.invoke(main, ['--start-date', start, '--end-date', end])
    assert result.exit_code == 0
    
    instance = mock_source.return_value
    instance.fetch_event_list.assert_called_with(start, end)

def test_date_limit_exceeded():
    runner = CliRunner()
    start = "2024-01-01"
    end = "2026-01-01" # > 15 months
    result = runner.invoke(main, ['--start-date', start, '--end-date', end])
    assert result.exit_code != 0
    assert "Date range cannot exceed 15 months" in result.output
