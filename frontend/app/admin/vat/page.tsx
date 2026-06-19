'use client';

import { useState } from 'react';
import { useAuth } from '@clerk/nextjs';

export default function VATReports() {
  const [quarter, setQuarter] = useState('');
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<{ quarter: string; xml: string } | null>(null);
  const { getToken } = useAuth();

  const currentYear = new Date().getFullYear();
  const quarters = [];
  for (let year = currentYear; year >= currentYear - 2; year--) {
    for (let q = 4; q >= 1; q--) {
      quarters.push(`${year}-Q${q}`);
    }
  }

  async function generateReport() {
    if (!quarter) return;

    setLoading(true);
    try {
      const token = await getToken();
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/admin/vat/report?quarter=${quarter}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) throw new Error('Failed to generate report');

      const data = await response.json();
      setReport(data);
    } catch (error) {
      console.error('Error generating report:', error);
      alert('Failed to generate VAT report');
    } finally {
      setLoading(false);
    }
  }

  function downloadXML() {
    if (!report) return;

    const blob = new Blob([report.xml], { type: 'application/xml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `vat-moss-${report.quarter}.xml`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">VAT Reports</h1>
        <p className="text-zinc-400">Generate VAT MOSS reports for EU compliance</p>
      </div>

      {/* Report Generator */}
      <div className="bg-zinc-900 rounded-lg p-6 border border-zinc-800">
        <h2 className="text-xl font-bold text-white mb-4">Generate Report</h2>

        <div className="space-y-4">
          <div>
            <label className="block text-sm text-zinc-400 mb-2">
              Select Quarter
            </label>
            <select
              value={quarter}
              onChange={(e) => setQuarter(e.target.value)}
              className="w-full px-4 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white focus:outline-none focus:border-zinc-600"
            >
              <option value="">Choose a quarter...</option>
              {quarters.map((q) => (
                <option key={q} value={q}>
                  {q}
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={generateReport}
            disabled={!quarter || loading}
            className="w-full px-6 py-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Generating...' : 'Generate VAT MOSS XML'}
          </button>
        </div>
      </div>

      {/* Report Display */}
      {report && (
        <div className="bg-zinc-900 rounded-lg p-6 border border-zinc-800">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold text-white">
              Report for {report.quarter}
            </h2>
            <button
              onClick={downloadXML}
              className="px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 transition-colors"
            >
              📥 Download XML
            </button>
          </div>

          <div className="bg-zinc-950 rounded-lg p-4 overflow-x-auto">
            <pre className="text-xs text-zinc-300 font-mono whitespace-pre-wrap">
              {report.xml}
            </pre>
          </div>
        </div>
      )}

      {/* Information */}
      <div className="bg-blue-500/10 border border-blue-500/50 rounded-lg p-6">
        <h3 className="text-lg font-bold text-blue-400 mb-2">
          ℹ️ VAT MOSS Information
        </h3>
        <div className="text-sm text-blue-300 space-y-2">
          <p>
            VAT MOSS (Mini One Stop Shop) allows you to report VAT on digital
            services to all EU member states through a single portal.
          </p>
          <p>
            <strong>Deadlines:</strong> Reports must be submitted by the 20th day
            of the month following the end of the quarter.
          </p>
          <p>
            <strong>Quarters:</strong>
          </p>
          <ul className="list-disc list-inside ml-4">
            <li>Q1: January - March (Due: April 20)</li>
            <li>Q2: April - June (Due: July 20)</li>
            <li>Q3: July - September (Due: October 20)</li>
            <li>Q4: October - December (Due: January 20)</li>
          </ul>
          <p>
            <strong>Submission:</strong> Upload the generated XML file to your
            country's VAT MOSS portal.
          </p>
        </div>
      </div>
    </div>
  );
}
