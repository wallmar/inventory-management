<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div class="card budget-card">
        <div class="budget-header">
          <label class="budget-label" for="restocking-budget">{{ t('restocking.budget') }}</label>
          <span class="budget-value">{{ money(budget) }}</span>
        </div>
        <input
          id="restocking-budget"
          v-model.number="budget"
          class="budget-slider"
          type="range"
          min="0"
          :max="maxBudget"
          step="100"
        />
        <div class="budget-meta">
          <span>{{ t('restocking.budgetHint') }}</span>
          <strong>{{ t('restocking.remaining', { amount: money(remaining) }) }}</strong>
        </div>
      </div>

      <div class="stats-grid">
        <div class="stat-card info">
          <div class="stat-label">{{ t('restocking.budget') }}</div>
          <div class="stat-value">{{ money(budget) }}</div>
        </div>
        <div class="stat-card success">
          <div class="stat-label">{{ t('restocking.selectedCost') }}</div>
          <div class="stat-value">{{ money(selectedCost) }}</div>
        </div>
        <div class="stat-card warning">
          <div class="stat-label">{{ t('restocking.itemsSelected') }}</div>
          <div class="stat-value">{{ selectedItems.length }} / {{ rows.length }}</div>
        </div>
        <div class="stat-card danger">
          <div class="stat-label">{{ t('restocking.maxLeadTime') }}</div>
          <div class="stat-value">{{ maxLeadTime === null ? '-' : t('orders.daysValue', { days: maxLeadTime }) }}</div>
        </div>
      </div>

      <div v-if="placedOrder" class="banner banner-success">
        <span>{{ t('restocking.orderPlaced', { number: placedOrder.order_number, date: formatDate(placedOrder.expected_delivery) }) }}</span>
        <router-link to="/orders" class="banner-link">{{ t('restocking.viewOrders') }}</router-link>
      </div>
      <div v-if="submitError" class="banner banner-error">{{ submitError }}</div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.recommendations') }}</h3>
          <div class="order-actions">
            <span v-if="selectedItems.length === 0" class="order-hint">{{ t('restocking.noSelection') }}</span>
            <button
              type="button"
              class="btn-primary"
              :disabled="selectedItems.length === 0 || submitting || alreadyPlaced"
              @click="placeOrder"
            >
              {{ submitting ? t('restocking.placing') : t('restocking.placeOrder') }}
            </button>
          </div>
        </div>
        <div v-if="rows.length === 0" class="empty-state">{{ t('restocking.noCandidates') }}</div>
        <div v-else class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('restocking.table.sku') }}</th>
                <th>{{ t('restocking.table.itemName') }}</th>
                <th>{{ t('restocking.table.category') }}</th>
                <th>{{ t('restocking.table.trend') }}</th>
                <th>{{ t('restocking.table.onHand') }}</th>
                <th>{{ t('restocking.table.forecast') }}</th>
                <th>{{ t('restocking.table.quantity') }}</th>
                <th>{{ t('restocking.table.unitCost') }}</th>
                <th>{{ t('restocking.table.lineCost') }}</th>
                <th>{{ t('restocking.table.leadTime') }}</th>
                <th>{{ t('restocking.table.status') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in rows" :key="row.item_sku" :class="{ 'row-over': !row.included }">
                <td><strong>{{ row.item_sku }}</strong></td>
                <td>{{ row.item_name }}</td>
                <td>{{ categoryLabel(row.category) }}</td>
                <td>
                  <span :class="['badge', row.trend]">{{ t(`trends.${row.trend}`) }}</span>
                </td>
                <td>{{ row.quantity_on_hand }}</td>
                <td>{{ row.forecasted_demand }}</td>
                <td><strong>{{ row.recommended_quantity }}</strong></td>
                <td>{{ unitPrice(row.unit_cost) }}</td>
                <td><strong>{{ money(row.line_cost) }}</strong></td>
                <td>{{ t('orders.daysValue', { days: row.lead_time_days }) }}</td>
                <td>
                  <span :class="['badge', row.included ? 'success' : 'danger']">
                    {{ row.included ? t('restocking.included') : t('restocking.overBudget') }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted } from 'vue'
import { api } from '../api'
import { useFilters } from '../composables/useFilters'
import { useI18n } from '../composables/useI18n'
import { formatCurrency, formatCurrencyWithDecimals } from '../utils/currency'

const CATEGORY_KEYS = {
  'Circuit Boards': 'circuitBoards',
  'Sensors': 'sensors',
  'Actuators': 'actuators',
  'Controllers': 'controllers',
  'Power Supplies': 'powerSupplies'
}

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency, currentLocale } = useI18n()
    const { selectedCategory } = useFilters()

    const loading = ref(true)
    const error = ref(null)
    const candidates = ref([])
    const budget = ref(0)
    const submitting = ref(false)
    const submitError = ref(null)
    const placedOrder = ref(null)
    const budgetInitialised = ref(false)
    const placedSelectionKey = ref(null)

    const money = (amount) => formatCurrency(amount, currentCurrency.value)
    const unitPrice = (amount) => formatCurrencyWithDecimals(amount, currentCurrency.value, 2)

    const categoryLabel = (category) => {
      const key = CATEGORY_KEYS[category]
      return key ? t(`categories.${key}`) : category
    }

    const formatDate = (dateString) => {
      const date = new Date(dateString)
      if (isNaN(date.getTime())) return dateString
      const locale = currentLocale.value === 'ja' ? 'ja-JP' : 'en-US'
      return date.toLocaleDateString(locale, { year: 'numeric', month: 'short', day: 'numeric' })
    }

    const maxBudget = computed(() => {
      const total = candidates.value.reduce((sum, c) => sum + c.line_cost, 0)
      return Math.ceil(total / 100) * 100
    })

    // First-fit greedy selection: candidates arrive sorted by priority. A line
    // that does not fit the remaining budget is marked over budget, but we keep
    // walking so cheaper, lower-priority lines can still use the leftover budget.
    // Sums run in integer cents so a line that exactly fits is not lost to float error
    const rows = computed(() => {
      const budgetCents = Math.round(budget.value * 100)
      let runningCents = 0
      return candidates.value.map(c => {
        const lineCents = Math.round(c.line_cost * 100)
        const included = runningCents + lineCents <= budgetCents
        if (included) runningCents += lineCents
        return { ...c, included }
      })
    })

    const selectedItems = computed(() => rows.value.filter(r => r.included))
    const selectedCost = computed(() => selectedItems.value.reduce((sum, r) => sum + Math.round(r.line_cost * 100), 0) / 100)
    const selectionKey = computed(() => selectedItems.value.map(r => r.item_sku).join(','))
    // The same selection was just submitted; block an accidental second order until it changes
    const alreadyPlaced = computed(() => placedSelectionKey.value === selectionKey.value)
    const remaining = computed(() => budget.value - selectedCost.value)
    const maxLeadTime = computed(() => {
      if (selectedItems.value.length === 0) return null
      return Math.max(...selectedItems.value.map(r => r.lead_time_days))
    })

    const load = async () => {
      try {
        loading.value = true
        error.value = null
        placedOrder.value = null
        submitError.value = null
        placedSelectionKey.value = null
        candidates.value = await api.getRestockingCandidates({ category: selectedCategory.value })
        const max = maxBudget.value
        if (!budgetInitialised.value) {
          budget.value = Math.round(max / 2 / 100) * 100
          budgetInitialised.value = true
        } else if (budget.value > max) {
          budget.value = max
        }
      } catch (err) {
        error.value = t('restocking.loadError') + ': ' + err.message
      } finally {
        loading.value = false
      }
    }

    const placeOrder = async () => {
      if (selectedItems.value.length === 0 || submitting.value) return
      submitting.value = true
      submitError.value = null
      placedOrder.value = null
      try {
        placedOrder.value = await api.createRestockingOrder({
          budget: budget.value,
          items: selectedItems.value.map(c => ({
            item_sku: c.item_sku,
            quantity: c.recommended_quantity
          }))
        })
        placedSelectionKey.value = selectionKey.value
      } catch (err) {
        const detail = err.response?.data?.detail
        // FastAPI validation errors (422) return a list of objects instead of a string
        submitError.value = Array.isArray(detail)
          ? detail.map(d => d.msg).join('; ')
          : detail || err.message
      } finally {
        submitting.value = false
      }
    }

    watch(selectedCategory, load)
    onMounted(load)

    return {
      t,
      loading,
      error,
      budget,
      maxBudget,
      rows,
      selectedItems,
      selectedCost,
      remaining,
      maxLeadTime,
      submitting,
      submitError,
      placedOrder,
      alreadyPlaced,
      money,
      unitPrice,
      categoryLabel,
      formatDate,
      placeOrder
    }
  }
}
</script>

<style scoped>
.budget-card {
  padding: 1.5rem;
  margin-bottom: 1.5rem;
}

.budget-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 1rem;
  margin-bottom: 0.75rem;
}

.budget-label {
  font-size: 0.875rem;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.budget-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: #0f172a;
}

.budget-slider {
  width: 100%;
  accent-color: #0f172a;
  cursor: pointer;
}

.budget-meta {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 0.5rem;
  margin-top: 0.75rem;
  font-size: 0.875rem;
  color: #64748b;
}

.budget-meta strong {
  color: #0f172a;
}

.banner {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.875rem 1rem;
  border-radius: 8px;
  margin-bottom: 1.5rem;
  font-size: 0.875rem;
}

.banner-success {
  background: #d1fae5;
  border: 1px solid #10b981;
  color: #065f46;
}

.banner-error {
  background: #fee2e2;
  border: 1px solid #ef4444;
  color: #991b1b;
}

.banner-link {
  color: inherit;
  font-weight: 600;
  text-decoration: underline;
}

.order-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
}

.order-hint {
  font-size: 0.813rem;
  color: #64748b;
}

.btn-primary {
  background: #0f172a;
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 0.5rem 1.25rem;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s, opacity 0.2s;
}

.btn-primary:hover:not(:disabled) {
  background: #1e293b;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.row-over {
  opacity: 0.55;
}

.empty-state {
  padding: 2rem;
  text-align: center;
  color: #64748b;
}
</style>
