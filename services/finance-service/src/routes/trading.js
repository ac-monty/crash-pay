import express from 'express';
import db from '../models/index.js';

const router = express.Router();
const { StockOrder, StockHolding } = db;

router.get('/positions', async (req, res) => {
    try {
        const positions = await StockHolding.findAll();
        res.json(positions);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Unable to fetch positions' });
    }
});

router.get('/orders', async (req, res) => {
    try {
        const orders = await StockOrder.findAll();
        res.json(orders);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Unable to fetch orders' });
    }
});

router.post('/orders', async (req, res) => {
    try {
        const order = await StockOrder.create(req.body);
        // naive immediate fill
        order.status = 'FILLED';
        await order.save();

        // update holding
        let holding = await StockHolding.findOne({ where: { userId: order.userId, symbol: order.symbol } });
        if (!holding) {
            holding = await StockHolding.create({ userId: order.userId, symbol: order.symbol, shares: 0, avgPrice: order.price });
        }
        const qty = parseFloat(order.quantity);
        if (order.side === 'BUY') {
            holding.avgPrice = ((holding.avgPrice * holding.shares) + (order.price * qty)) / (parseFloat(holding.shares) + qty);
            holding.shares = parseFloat(holding.shares) + qty;
        } else {
            holding.shares = Math.max(0, parseFloat(holding.shares) - qty);
        }
        await holding.save();

        res.status(201).json(order);
    } catch (err) {
        console.error(err);
        res.status(400).json({ error: err.message });
    }
});

router.get('/orders', async (req, res) => {
    try {
        const orders = await StockOrder.findAll();
        res.json(orders);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Unable to fetch orders' });
    }
});

router.put('/orders/:id/cancel', async (req, res) => {
    try {
        const order = await StockOrder.findByPk(req.params.id);
        if (!order) return res.status(404).json({ error: 'Not found' });
        order.status = 'CANCELLED';
        await order.save();
        res.json(order);
    } catch (err) {
        console.error(err);
        res.status(400).json({ error: 'Unable to cancel' });
    }
});

router.get('/positions', async (req, res) => {
    try {
        const holdings = await StockHolding.findAll();
        res.json(holdings);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Unable to fetch holdings' });
    }
});

export default router;