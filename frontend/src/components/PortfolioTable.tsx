import React from 'react';

const PortfolioTable = () => {
    // TODO: Replace with data from API
    const positions = [
        { symbol: "SBIN.NS", qty: 50, avgPrice: 600.50, lastPrice: 602.00, pnlPct: 0.25 },
        { symbol: "INFY.NS", qty: 10, avgPrice: 1500.00, lastPrice: 1495.00, pnlPct: -0.33 },
    ];

    return (
        <div className="bg-gray-800 p-4 rounded-lg shadow">
            <h2 className="text-lg font-semibold mb-4">Open Positions</h2>
            <div className="overflow-x-auto">
                <table className="min-w-full">
                    <thead>
                        <tr className="border-b border-gray-700">
                            <th className="text-left p-2">Symbol</th>
                            <th className="text-right p-2">Qty</th>
                            <th className="text-right p-2">Avg. Price</th>
                            <th className="text-right p-2">Last Price</th>
                            <th className="text-right p-2">P&L %</th>
                        </tr>
                    </thead>
                    <tbody>
                        {positions.map(pos => (
                            <tr key={pos.symbol} className="border-b border-gray-700">
                                <td className="p-2">{pos.symbol}</td>
                                <td className="text-right p-2">{pos.qty}</td>
                                <td className="text-right p-2">{pos.avgPrice.toFixed(2)}</td>
                                <td className="text-right p-2">{pos.lastPrice.toFixed(2)}</td>
                                <td className={`text-right p-2 ${pos.pnlPct >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                                    {pos.pnlPct.toFixed(2)}%
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default PortfolioTable;