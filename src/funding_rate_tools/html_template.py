from json import dumps

def get_html_content(pairs_data: list[dict]) -> str:
    """
    Generates an interactive HTML dashboard with dynamic period and rolling P.A. controls.
    Expects pairs_data list containing for each symbol:
      symbol, current_price, pa_rate_7d, pa_rate_14d, all_rates_data (list of {time, rate}).
    """
    # Prepare data payload for JavaScript
    data_js = {pair['symbol']: pair['all_rates_data'] for pair in pairs_data}
    summaries_js = {pair['symbol']: {'current_price': pair['current_price'], 'pa7': pair['pa_rate_7d'], 'pa14': pair['pa_rate_14d']} for pair in pairs_data}

    data_json = dumps(data_js)
    summaries_html = ''.join([
        f"<div class='summary'><h2>{p['symbol']}</h2>"
        f"<p>Price: ${p['current_price']}</p>"
        f"<p>7D p.a.: {'{:.2f}'.format(p['pa_rate_7d']) if p['pa_rate_7d'] is not None else 'N/A'}%</p>"
        f"<p>14D p.a.: {'{:.2f}'.format(p['pa_rate_14d']) if p['pa_rate_14d'] is not None else 'N/A'}%</p>"
        f"</div>"
        for p in pairs_data
    ])
    charts_html = ''.join([
        f"<div class='chart-container'><h3>{p['symbol']} Funding Rate & Rolling P.A.</h3>"
        f"<canvas id='chart_{i}'></canvas>"
        f"<div class='yield-input'><label>Yield (P.A. %):"
        f"<span class=\"tooltip\">?"
          f"<span class=\"tooltiptext\">"
            f"Your expected staking yield (% p.a.); added to funding to compute net returns."
          f"</span>"
        f"</span>"
        f"<input type='number' id='yieldInput_{i}' placeholder='Enter yield' style='width:60px; padding:5px; margin-top:10px;'></label></div></div>"
        for i, p in enumerate(pairs_data)
    ])

    # Create symbol to index mapping for JavaScript
    symbol_to_index = {p['symbol']: i for i, p in enumerate(pairs_data)}

    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Funding Rate Dashboard</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
        <script>
            Chart.register({
                id: 'zeroLine',
                afterDraw(chart) {
                    const {ctx, scales} = chart;
                    if (!scales.paAxis) return;
                    const yZero = scales.paAxis.getPixelForValue(0);
                    ctx.save();
                    ctx.beginPath();
                    ctx.moveTo(scales.x.left, yZero);
                    ctx.lineTo(scales.x.right, yZero);
                    ctx.lineWidth = 1;
                    ctx.strokeStyle = '#888';
                    ctx.stroke();
                    ctx.restore();
                }
            });
        </script>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css">
        <script src="https://cdn.jsdelivr.net/npm/flatpickr"></script>
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f4f4f4; color: #333; }
            header { background-color: #0b1e35; color: white; padding: 15px 0; text-align: center; margin-bottom: 20px; }
            .controls { margin-bottom: 20px; display: flex; flex-wrap: wrap; gap: 10px; justify-content: center; align-items: center; }
            .controls label { display: flex; align-items: center; gap: 5px;}
            .controls select, .controls input[type="checkbox"] { padding: 5px; margin-left: 5px; }
            .container { max-width: 1600px; margin: auto; } /* Increased max-width for potentially wider layout */
            .summaries-container { display: flex; flex-wrap: wrap; gap: 20px; margin-bottom: 30px; justify-content: center; }
            .summary { background-color: #e9ecef; padding: 15px; border-radius: 5px; flex: 1; min-width: 250px; max-width: 300px; }
            .summary h2 { margin-top: 0; color: #007bff; }
            .summary p { color: #333; } /* Ensure summary text is dark */
            .charts-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(600px, 1fr)); gap: 20px; } /* Wider min chart width */
            .chart-container { background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.05); }
            .tooltip { position: relative; display: inline-block; cursor: help; margin-left:5px; }
            .tooltip .tooltiptext {
                visibility: hidden; width: 200px; background: #555; color: #fff;
                text-align: center; border-radius: 6px; padding: 5px;
                position: absolute; z-index: 1; bottom: 125%; left: 50%;
                margin-left: -100px; opacity: 0; transition: opacity 0.3s;
            }
            .tooltip:hover .tooltiptext { visibility: visible; opacity: 1; }
        </style>
    </head>
    <body>
        <header>
            <h1>Funding Rate Dashboard</h1>
            <div class="controls">
                <label>View Period:
                    <select id="periodSelect">
                        <option value="7">7 Days</option>
                        <option value="30">1 Month</option>
                        <option value="90" selected>3 Months</option>
                        <option value="180">6 Months</option>
                        <option value="365">1 Year</option>
                        <option value="0">All</option>
                        <option value="custom">Custom</option>
                    </select>
                    <span class="tooltip">?
                        <span class="tooltiptext">
                            Choose a preset or custom timeframe.
                        </span>
                    </span>
                </label>
                <label id="customRangeControls" style="display:none; margin-left:10px">
                    From:
                    <input type="text" id="customStart" class="datePicker" placeholder="YYYY-MM-DD" style="width:110px; padding:3px;"/>
                    To:
                    <input type="text" id="customEnd"   class="datePicker" placeholder="YYYY-MM-DD" style="width:110px; padding:3px;"/>
                    <span class="tooltip">?
                        <span class="tooltiptext">
                            Pick start/end dates (YYYY-MM-DD); limited to available data.
                        </span>
                    </span>
                </label>
                <label>P.A. Window:
                    <select id="paWindowSelect">
                        <option value="1" selected>1 Day</option>
                        <option value="7">7 Days</option>
                        <option value="14">14 Days</option>
                    </select>
                    <span class="tooltip">?
                        <span class="tooltiptext">
                            Span over which rolling annualized funding rate is calculated.
                        </span>
                    </span>
                </label>
                <label>
                    <input type="checkbox" id="showFundingRate" checked> Show Funding %
                    <span class="tooltip">?
                        <span class="tooltiptext">
                            Actual funding payments each interval (not annualized); shows funding volatility.
                        </span>
                    </span>
                </label>
                <label>
                    <input type="checkbox" id="showPaRate" checked> Show p.a. funding rate
                    <span class="tooltip">?
                        <span class="tooltiptext">
                            Rolling annualized funding rate (% p.a.) over the selected window.
                        </span>
                    </span>
                </label>
                <label>
                    <input type="checkbox" id="showCumulativeNetPa" checked> Show cumulative hedged P.A. %
                    <span class="tooltip">?
                        <span class="tooltiptext">
                            Cumulative net return (funding + yield) annualized to date.<br>
                            At time t, it's the average net rate so far, annualized; area under curve ≈ total hedged yield.
                        </span>
                    </span>
                </label>
                <label>
                    <input type="checkbox" id="showInstantNetPa" checked> Show instant hedged P.A. %
                    <span class="tooltip">?
                        <span class="tooltiptext">
                            Windowed net rate (funding + yield) annualized over the P.A. window.<br>
                            At each point, you see your w-day average net P.A.; higher window smooths spikes.
                        </span>
                    </span>
                </label>
            </div>
            <div class="summaries-container">
                """ + summaries_html + """
            </div>
        </header>
        <div class="container">
            <div class="charts-grid">
                """ + charts_html + """
            </div>
        </div>
        <script>
            const fundingData = """ + data_json + """;
            const fundingIntervals = """ + dumps({p['symbol']: p['interval_hours'] for p in pairs_data}) + """;
            const symbolToIndex = """ + dumps(symbol_to_index) + """;
            const periodSelect = document.getElementById('periodSelect');
            const paWindowSelect = document.getElementById('paWindowSelect');
            const showFundingRateCheckbox = document.getElementById('showFundingRate');
            const showPaRateCheckbox = document.getElementById('showPaRate');
            const showCumulativeCheckbox = document.getElementById('showCumulativeNetPa');
            const showInstantCheckbox = document.getElementById('showInstantNetPa');
            let yieldInputs = [];
            const charts = [];

            function calculateHedgedYieldPaSeries(data, yieldPa, interval) {
                if (!data.length || isNaN(yieldPa)) return [];
                const intervalsPerDay = 24 / interval;
                const annualFactor = intervalsPerDay * 365;
                const perInterval = (yieldPa/100) / annualFactor;
                let sum = 0;
                return data.map((d, i) => {
                    sum += perInterval + d.rate;
                    const avg = sum/(i+1);
                    return { x: d.time, y: avg * annualFactor * 100 };
                });
            }

            function calculateInstantHedgedPaSeries(data, yieldPa, interval, windowDays) {
                if (!data.length || isNaN(yieldPa)) return [];
                const intervalsPerDay = 24/interval;
                const yieldPerInterval = (yieldPa/100)/(intervalsPerDay*365);
                const factor = intervalsPerDay * 365 * 100;
                return data.map(d => {
                    const start = d.time - windowDays*24*60*60*1000;
                    const windowData = data.filter(x => x.time>=start && x.time<=d.time);
                    const sum = windowData.reduce((acc,x)=>acc + x.rate + yieldPerInterval, 0);
                    const avg = windowData.length ? sum/windowData.length : 0;
                    return { x: d.time, y: avg * factor };
                });
            }

            function filterData(data, days) {
                if (days === 0) return data;
                const now = Date.now();
                const cutoff = now - days * 24 * 60 * 60 * 1000;
                return data.filter(d => d.time >= cutoff);
            }

            function calculatePaSeries(data, windowDays, interval) {
                const result = [];
                const intervalsPerDay = 24 / interval;
                const factor = intervalsPerDay * 365 * 100;
                for (let i = 0; i < data.length; i++) {
                    const end = data[i].time;
                    const start = end - windowDays * 24 * 60 * 60 * 1000;
                    const windowData = data.filter(d => d.time >= start && d.time <= end);
                    const sum = windowData.reduce((acc, d) => acc + d.rate, 0);
                    const avg = windowData.length ? sum / windowData.length : 0;
                    result.push({ x: end, y: avg * factor });
                }
                return result;
            }

            function createOrUpdateCharts() {
                const periodVal = periodSelect.value;
                let periodDays = null, customRange = null;
                if (periodVal === 'custom') {
                    const s = customStart.value, e = customEnd.value;
                    const startMs = new Date(s + "T00:00:00").getTime();
                    const endMs   = new Date(e + "T23:59:59").getTime();
                    customRange = { start: startMs, end: endMs };
                } else {
                    periodDays = parseInt(periodVal);
                }
                const paWindow = parseInt(paWindowSelect.value);
                const showFunding = showFundingRateCheckbox.checked;
                const showPa = showPaRateCheckbox.checked;

                Object.keys(fundingData).forEach((symbol, idx) => {
                    const interval = fundingIntervals[symbol];
                    const raw = fundingData[symbol];
                    const filtered = customRange
                        ? raw.filter(d => d.time >= customRange.start && d.time <= customRange.end)
                        : filterData(raw, periodDays);

                    const rateSeries = filtered.map(d => ({ x: d.time, y: d.rate * 100 }));
                    const paSeries   = calculatePaSeries(filtered, paWindow, interval);
                    const yieldVal      = parseFloat(yieldInputs[idx].value);
                    const hedgedSeries  = calculateHedgedYieldPaSeries(filtered, yieldVal, interval);
                    const instantSeries = calculateInstantHedgedPaSeries(filtered, yieldVal, interval, paWindow);
                    const showCumulative = showCumulativeCheckbox.checked && !isNaN(yieldVal);
                    const showInstant    = showInstantCheckbox.checked && !isNaN(yieldVal);

                    const visibleFunding = showFunding ? rateSeries.map(p => Math.abs(p.y)) : [];
                    const visiblePa      = showPa      ? paSeries.map(p => Math.abs(p.y))      : [];
                    const visibleCum     = showCumulative ? hedgedSeries.map(p => Math.abs(p.y))    : [];
                    const visibleInst    = showInstant    ? instantSeries.map(p => Math.abs(p.y))    : [];
                    const maxRate = visibleFunding.length ? Math.max(...visibleFunding) : 0;
                    const rateMin = -maxRate, rateMax = maxRate;
                    const allPa = [...visiblePa, ...visibleCum, ...visibleInst];
                    const maxPa = allPa.length ? Math.max(...allPa) : 0;
                    const paMin = -maxPa, paMax = maxPa;

                    if (charts[idx]) {
                        charts[idx].data.labels            = rateSeries.map(p => p.x);
                        charts[idx].data.datasets[0].data  = rateSeries;
                        charts[idx].data.datasets[0].hidden = !showFunding;
                        charts[idx].data.datasets[1].data  = paSeries;
                        charts[idx].data.datasets[1].hidden = !showPa;
                        if (charts[idx].data.datasets.length > 2) {
                            charts[idx].data.datasets[2].data   = hedgedSeries;
                            charts[idx].data.datasets[2].hidden = !showCumulative;
                        }
                        if (charts[idx].data.datasets.length > 3) {
                            charts[idx].data.datasets[3].data   = instantSeries;
                            charts[idx].data.datasets[3].hidden = !showInstant;
                        }
                        charts[idx].options.scales.rateAxis.min = rateMin;
                        charts[idx].options.scales.rateAxis.max = rateMax;
                        charts[idx].options.scales.paAxis.min   = paMin;
                        charts[idx].options.scales.paAxis.max   = paMax;
                        charts[idx].update();
                    } else {
                        const ctx = document.getElementById(`chart_${idx}`).getContext('2d');
                        charts[idx] = new Chart(ctx, {
                            type: 'line',
                            plugins: ['zeroLine'],
                            data: {
                                labels: rateSeries.map(p => p.x),
                                datasets: [
                                    {
                                        label: symbol + ' Funding %',
                                        data: rateSeries,
                                        borderColor: 'rgb(75,192,192)',
                                        yAxisID: 'rateAxis',
                                        tension: 0.1,
                                        fill: false,
                                        hidden: !showFunding
                                    },
                                    {
                                        label: symbol + ' P.A. %',
                                        data: paSeries,
                                        borderColor: 'rgb(255,99,132)',
                                        yAxisID: 'paAxis',
                                        tension: 0.1,
                                        fill: false,
                                        hidden: !showPa
                                    },
                                    {
                                        label: symbol + ' Net P.A. %',
                                        data: hedgedSeries,
                                        borderColor: 'rgb(153,102,255)',
                                        yAxisID: 'paAxis',
                                        tension: 0.1,
                                        fill: false,
                                        hidden: !showCumulative
                                    },
                                    {
                                        label: symbol+' Instant Net P.A. %',
                                        data: instantSeries,
                                        borderColor: 'rgb(54,162,235)',
                                        yAxisID: 'paAxis',
                                        tension: 0.1,
                                        fill: false,
                                        hidden: !showInstant
                                    }
                                ]
                            },
                            options: {
                                responsive: true,
                                maintainAspectRatio: true,
                                aspectRatio: 1.75,
                                scales: {
                                    x: { type: 'time', time: { unit: 'day' } },
                                    rateAxis: {
                                        type: 'linear',
                                        position: 'left',
                                        title: { display: true, text: '% Funding' },
                                        ticks: { padding: 5, beginAtZero: true },
                                        grace: '5%',
                                        min: rateMin,
                                        max: rateMax
                                    },
                                    paAxis: {
                                        type: 'linear',
                                        position: 'right',
                                        title: { display: true, text: '% p.a.' },
                                        grid: { drawOnChartArea: false },
                                        ticks: { padding: 5, beginAtZero: true },
                                        grace: '5%',
                                        min: paMin,
                                        max: paMax
                                    }
                                },
                                plugins: { tooltip: { mode: 'index', intersect: false } },
                                interaction: { mode: 'index', intersect: false }
                            }
                        });
                    }
                });
            }

            // Parse URL parameters and prefill yield inputs
            function parseUrlParams() {
                const urlParams = new URLSearchParams(window.location.search);
                const yieldParams = {};

                for (const [key, value] of urlParams.entries()) {
                    if (key.startsWith('yield_')) {
                        const symbol = key.substring(6); // Remove 'yield_' prefix
                        yieldParams[symbol] = parseFloat(value);
                    }
                }

                return yieldParams;
            }

            function prefillYieldInputs() {
                const yieldParams = parseUrlParams();

                for (const [symbol, yieldValue] of Object.entries(yieldParams)) {
                    const index = symbolToIndex[symbol];
                    if (index !== undefined && !isNaN(yieldValue)) {
                        const input = document.getElementById(`yieldInput_${index}`);
                        if (input) {
                            input.value = yieldValue.toFixed(2);
                        }
                    }
                }
            }

            window.onload = () => {
                Object.keys(fundingData).forEach((_, idx) => {
                    const inp = document.getElementById(`yieldInput_${idx}`);
                    yieldInputs[idx] = inp;
                    inp.addEventListener('input', createOrUpdateCharts);
                });

                // Prefill inputs before creating charts
                prefillYieldInputs();
                createOrUpdateCharts();
            };

            periodSelect.addEventListener('change', createOrUpdateCharts);
            paWindowSelect.addEventListener('change', createOrUpdateCharts);
            showFundingRateCheckbox.addEventListener('change', createOrUpdateCharts);
            showPaRateCheckbox.addEventListener('change', createOrUpdateCharts);
            showCumulativeCheckbox.addEventListener('change', createOrUpdateCharts);
            showInstantCheckbox.addEventListener('change', createOrUpdateCharts);

            const customControls = document.getElementById('customRangeControls');
            const customStart    = document.getElementById('customStart');
            const customEnd      = document.getElementById('customEnd');
            const today2 = new Date(), threeMo2 = new Date();
            threeMo2.setMonth(today2.getMonth()-3);
            const todayStr   = today2.toISOString().slice(0,10);
            const threeMoStr = threeMo2.toISOString().slice(0,10);
            flatpickr("#customStart", {dateFormat:"Y-m-d", defaultDate: threeMoStr, maxDate: todayStr});
            flatpickr("#customEnd",   {dateFormat:"Y-m-d", defaultDate: todayStr,   maxDate: todayStr});
            periodSelect.addEventListener('change', ()=>{
                if (periodSelect.value==='custom') customControls.style.display='inline-flex';
                else customControls.style.display='none';
                createOrUpdateCharts();
            });
            document.querySelectorAll(".datePicker")
                .forEach(inp => inp.addEventListener("change", createOrUpdateCharts));
        </script>
    </body>
    </html>
    """
