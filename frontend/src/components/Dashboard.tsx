import React from 'react';
import SummaryBar from './SummaryBar';
import PortfolioTable from './PortfolioTable';
import TradeTape from './TradeTape';
import PnLChart from './PnLChart';

const Dashboard = () => {
    // TODO: Fetch data from API endpoints
    return (
        <div className="space-y-6">
            <SummaryBar />
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2 space-y-6">
                    <PortfolioTable />
                    <TradeTape />
                </div>
                <div className="lg:col-span-1">
                    <PnLChart />
                </div>
            </div>
        </div>
    );
};

export default Dashboard;