import React from 'react';

const TradeTape = () => {
    // TODO: Replace with data from API
    const trades = [
        { time: "11:34:12", symbol: "SBIN.NS", side: "SELL", qty: 25, price: 603.10 },
        { time: "10:55:01", symbol: "INFY.NS", side: "BUY", qty: 10, price: 1500.00 },
        { time: "09:45:23", symbol: "SBIN.NS", side: "BUY", qty: 25, price: 600.50 },
    ];

    return (
        <div className="bg-gray-800 p-4 rounded-lg shadow">
            <h2 className="text-lg font-semibold mb-4">Today's Trades</h2>
            <div className="overflow-x-auto">
                <table className="min-w-full">
                    {/* ... table headers ... */}
                    <tbody>
                        {trades.map((trade, i) => (
                            <tr key={i} className="border-b border-gray-700 text-sm">
                                <td className="p-2">{trade.time}</td>
                                <td className="p-2">{trade.symbol}</td>
                                <td className={`p-2 ${trade.side === 'BUY' ? 'text-green-500' : 'text-red-500'}`}>{trade.side}</td>
                                <td className="text-right p-2">{trade.qty}</td>
                                <td className="text-right p-2">{trade.price.toFixed(2)}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default TradeTape;