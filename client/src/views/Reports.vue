<template>
  <div class="reports">
    <div class="page-header">
      <h2>{{ t('reports.title') }}</h2>
      <p>{{ t('reports.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('reports.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <!-- Quarterly Performance -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('reports.quarterlyPerformance') }}</h3>
        </div>
        <div v-if="quarterlyData.length === 0" class="loading">{{ t('reports.noData') }}</div>
        <div v-else class="table-container">
          <table class="reports-table">
            <thead>
              <tr>
                <th>{{ t('reports.quarter') }}</th>
                <th>{{ t('reports.totalOrders') }}</th>
                <th>{{ t('reports.totalRevenue') }}</th>
                <th>{{ t('reports.avgOrderValue') }}</th>
                <th>{{ t('reports.fulfillmentRate') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="q in quarterlyData" :key="q.quarter">
                <td><strong>{{ q.quarter }}</strong></td>
                <td>{{ q.total_orders }}</td>
                <td>{{ formatCurrency(q.total_revenue ?? 0, currentCurrency) }}</td>
                <td>{{ formatCurrency(q.avg_order_value ?? 0, currentCurrency) }}</td>
                <td>
                  <span :class="getFulfillmentClass(q.fulfillment_rate)">
                    {{ q.fulfillment_rate }}%
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Monthly Trends Chart -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('reports.monthlyRevenueTrend') }}</h3>
        </div>
        <div v-if="monthlyData.length === 0" class="loading">{{ t('reports.noData') }}</div>
        <div v-else class="chart-container">
          <div class="bar-chart">
            <div v-for="month in monthlyData" :key="month.month" class="bar-wrapper">
              <div class="bar-container">
                <div
                  class="bar"
                  role="img"
                  :aria-label="formatMonth(month.month) + ': ' + formatCurrency(month.revenue ?? 0, currentCurrency)"
                  :style="{ height: getBarHeight(month.revenue) + 'px' }"
                  :title="formatCurrency(month.revenue ?? 0, currentCurrency)"
                ></div>
              </div>
              <div class="bar-label">{{ formatMonth(month.month) }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Month-over-Month Comparison -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('reports.monthOverMonth') }}</h3>
        </div>
        <div v-if="monthlyData.length === 0" class="loading">{{ t('reports.noData') }}</div>
        <div v-else class="table-container">
          <table class="reports-table">
            <thead>
              <tr>
                <th>{{ t('reports.month') }}</th>
                <th>{{ t('reports.orders') }}</th>
                <th>{{ t('reports.revenue') }}</th>
                <th>{{ t('reports.change') }}</th>
                <th>{{ t('reports.growthRate') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(month, index) in monthlyData" :key="month.month">
                <td><strong>{{ formatMonth(month.month) }}</strong></td>
                <td>{{ month.order_count }}</td>
                <td>{{ formatCurrency(month.revenue ?? 0, currentCurrency) }}</td>
                <td>
                  <span v-if="index > 0" :class="getChangeClass(month.revenue, monthlyData[index - 1].revenue)">
                    {{ getChangeValue(month.revenue, monthlyData[index - 1].revenue) }}
                  </span>
                  <span v-else>-</span>
                </td>
                <td>
                  <span v-if="index > 0" :class="getChangeClass(month.revenue, monthlyData[index - 1].revenue)">
                    {{ getGrowthRate(month.revenue, monthlyData[index - 1].revenue) }}
                  </span>
                  <span v-else>-</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Summary Stats -->
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-label">{{ t('reports.totalRevenueYtd') }}</div>
          <div class="stat-value">{{ formatCurrency(totalRevenue, currentCurrency) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('reports.avgMonthlyRevenue') }}</div>
          <div class="stat-value">{{ formatCurrency(avgMonthlyRevenue, currentCurrency) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('reports.totalOrdersYtd') }}</div>
          <div class="stat-value">{{ totalOrders }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('reports.bestQuarter') }}</div>
          <div class="stat-value">{{ bestQuarter }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue'
import { api } from '../api'
import { useFilters } from '../composables/useFilters'
import { useI18n } from '../composables/useI18n'
import { formatCurrency } from '../utils/currency'

export default {
  name: 'Reports',
  setup() {
    const { t, currentCurrency, currentLocale } = useI18n()
    const loading = ref(true)
    const error = ref(null)
    const quarterlyData = ref([])
    const monthlyData = ref([])

    const {
      selectedPeriod,
      selectedLocation,
      selectedCategory,
      selectedStatus,
      getCurrentFilters
    } = useFilters()

    const loadData = async () => {
      try {
        loading.value = true
        error.value = null
        const filters = getCurrentFilters()
        const [quarterly, monthly] = await Promise.all([
          api.getQuarterlyReports(filters),
          api.getMonthlyTrends(filters)
        ])
        quarterlyData.value = quarterly
        monthlyData.value = monthly
      } catch (err) {
        error.value = t('reports.loadError') + ': ' + err.message
        console.error('Error loading reports:', err)
      } finally {
        loading.value = false
      }
    }

    const totalRevenue = computed(() =>
      monthlyData.value.reduce((sum, m) => sum + (m.revenue ?? 0), 0)
    )

    const avgMonthlyRevenue = computed(() =>
      monthlyData.value.length > 0 ? totalRevenue.value / monthlyData.value.length : 0
    )

    const totalOrders = computed(() =>
      monthlyData.value.reduce((sum, m) => sum + (m.order_count ?? 0), 0)
    )

    const bestQuarter = computed(() => {
      let best = '-'
      let bestRevenue = 0
      for (const q of quarterlyData.value) {
        if (q.total_revenue > bestRevenue) {
          bestRevenue = q.total_revenue
          best = q.quarter
        }
      }
      return best
    })

    const maxRevenue = computed(() =>
      monthlyData.value.reduce((max, m) => Math.max(max, m.revenue ?? 0), 0)
    )

    // Parse YYYY-MM safely; fall back to the raw string when invalid
    const formatMonth = (monthStr) => {
      if (typeof monthStr !== 'string') return String(monthStr ?? '')
      const match = /^(\d{4})-(\d{2})$/.exec(monthStr)
      if (!match) return monthStr
      const date = new Date(Number(match[1]), Number(match[2]) - 1, 1)
      if (isNaN(date.getTime())) return monthStr
      return date.toLocaleDateString(currentLocale.value === 'ja' ? 'ja-JP' : 'en-US', {
        year: 'numeric',
        month: 'short'
      })
    }

    // Bar height in px (max 200px)
    const getBarHeight = (revenue) => {
      if (maxRevenue.value === 0) return 0
      return ((revenue ?? 0) / maxRevenue.value) * 200
    }

    const getFulfillmentClass = (rate) => {
      if (rate >= 90) return 'badge success'
      if (rate >= 75) return 'badge warning'
      return 'badge danger'
    }

    // Signed change: sign + formatted absolute value
    const getChangeValue = (current, previous) => {
      const change = (current ?? 0) - (previous ?? 0)
      if (change > 0) return '+' + formatCurrency(change, currentCurrency.value)
      if (change < 0) return '-' + formatCurrency(Math.abs(change), currentCurrency.value)
      return formatCurrency(0, currentCurrency.value)
    }

    const getChangeClass = (current, previous) => {
      const change = (current ?? 0) - (previous ?? 0)
      if (change > 0) return 'positive-change'
      if (change < 0) return 'negative-change'
      return ''
    }

    const getGrowthRate = (current, previous) => {
      if (!previous) return '-'
      const rate = (((current ?? 0) - previous) / previous) * 100
      return (rate > 0 ? '+' : '') + rate.toFixed(1) + '%'
    }

    onMounted(() => {
      loadData()
    })

    watch([selectedPeriod, selectedLocation, selectedCategory, selectedStatus], () => {
      loadData()
    })

    return {
      t,
      currentCurrency,
      loading,
      error,
      quarterlyData,
      monthlyData,
      totalRevenue,
      avgMonthlyRevenue,
      totalOrders,
      bestQuarter,
      formatCurrency,
      formatMonth,
      getBarHeight,
      getFulfillmentClass,
      getChangeValue,
      getChangeClass,
      getGrowthRate
    }
  }
}
</script>

<style scoped>
.reports {
  padding: 0;
}

.card {
  background: white;
  border-radius: 12px;
  padding: 1.5rem;
  margin-bottom: 1.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.card-header {
  margin-bottom: 1.5rem;
}

.card-title {
  font-size: 1.25rem;
  font-weight: 600;
  color: #0f172a;
  margin: 0;
}

.reports-table {
  width: 100%;
  border-collapse: collapse;
}

.reports-table th {
  background: #f8fafc;
  padding: 0.75rem;
  text-align: left;
  font-weight: 600;
  color: #64748b;
  border-bottom: 2px solid #e2e8f0;
}

.reports-table td {
  padding: 0.75rem;
  border-bottom: 1px solid #e2e8f0;
}

.reports-table tr:hover {
  background: #f8fafc;
}

.chart-container {
  padding: 2rem 1rem;
  min-height: 300px;
}

.bar-chart {
  display: flex;
  align-items: flex-end;
  justify-content: space-around;
  height: 250px;
  gap: 0.5rem;
}

.bar-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
  max-width: 80px;
}

.bar-container {
  height: 200px;
  display: flex;
  align-items: flex-end;
  width: 100%;
}

.bar {
  width: 100%;
  background: linear-gradient(to top, #3b82f6, #60a5fa);
  border-radius: 4px 4px 0 0;
  transition: all 0.3s;
  cursor: pointer;
}

.bar:hover {
  background: linear-gradient(to top, #2563eb, #3b82f6);
}

.bar-label {
  margin-top: 0.5rem;
  font-size: 0.75rem;
  color: #64748b;
  text-align: center;
  transform: rotate(-45deg);
  white-space: nowrap;
  margin-top: 1.5rem;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1rem;
  margin-top: 1.5rem;
}

.stat-card {
  background: white;
  border-radius: 12px;
  padding: 1.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  border-left: 4px solid #3b82f6;
}

.stat-label {
  font-size: 0.875rem;
  color: #64748b;
  margin-bottom: 0.5rem;
}

.stat-value {
  font-size: 1.875rem;
  font-weight: 700;
  color: #0f172a;
}

.badge {
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.875rem;
  font-weight: 500;
}

.badge.success {
  background: #dcfce7;
  color: #166534;
}

.badge.warning {
  background: #fef3c7;
  color: #92400e;
}

.badge.danger {
  background: #fee2e2;
  color: #991b1b;
}

.positive-change {
  color: #16a34a;
  font-weight: 600;
}

.negative-change {
  color: #dc2626;
  font-weight: 600;
}

.loading {
  text-align: center;
  padding: 3rem;
  color: #64748b;
}

.error {
  background: #fee2e2;
  color: #991b1b;
  padding: 1rem;
  border-radius: 8px;
  margin: 1rem 0;
}
</style>
