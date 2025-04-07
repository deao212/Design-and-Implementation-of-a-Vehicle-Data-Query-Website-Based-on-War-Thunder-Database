<template>
  <div class="vehicle-list-container">
    <v-container class="pa-0">
      <div class="header-section">
        <h1 class="title">Vehicle Information System</h1>

        <!-- Filter controls with search and vehicle type selection -->
        <div class="filter-controls">
          <!-- Global search input field -->
          <v-text-field
            v-model="globalSearch"
            label="globalSearch"
            outlined
            dense
            clearable
            prepend-inner-icon="mdi-magnify"
            class="search-field"
            :style="{
              'min-width': smAndUp ? '300px' : '100%',
              'max-width': '400px'
            }"
          />

          <!-- Vehicle type selection dropdown -->
          <v-select
            v-model="selectedType"
            :items="vehicleTypes"
            item-title="text"
            item-value="value"
            label="Select Vehicle Type"
            outlined
            dense
            :disabled="isLoading"
            class="type-selector"
            :style="{
              'min-width': smAndUp ? '280px' : '100%',
              'max-width': '400px'
            }"
          />
        </div>
      </div>

      <!-- Server-side paginated data table -->
      <v-data-table-server
        ref="dataTable"
        v-model:items-per-page="itemsPerPage"
        :headers="processedHeaders"
        :items="serverItems"
        :items-length="totalItems"
        :loading="isLoading"
        :search="globalSearch"
        item-value="id"
        class="elevation-1 data-table"
        @update:options="loadItems"
      >

        <!-- Table header with loading indicator -->
        <template v-slot:top>
          <v-toolbar flat color="grey lighten-4">
            <v-toolbar-title class="font-weight-bold primary--text">Detailed Information</v-toolbar-title>
            <v-spacer></v-spacer>
            <v-progress-circular
              v-if="isLoading"
              indeterminate
              color="primary"
              size="24"
            ></v-progress-circular>
          </v-toolbar>
        </template>

        <!-- Custom row rendering template -->
        <template v-slot:item="{ item }">
          <tr>
            <td v-for="header in processedHeaders" :key="header.value">
              {{ formatValue(item, header.value) }}
            </td>
          </tr>
        </template>
      </v-data-table-server>
    </v-container>
  </div>
</template>

<script>
import { useDisplay } from 'vuetify'
import axios from 'axios';
import '@/assets/VehicleList.css'

export default {
  setup() {
    const { smAndUp } = useDisplay()
    return { smAndUp }
  },

  data() {
    return {
      isLoading: false,
      serverItems: [],
      totalItems: 0,
      itemsPerPage: 10,
      selectedType: 'aviation',
      globalSearch: '',
      vehicleTypes: [
        { text: 'aviation', value: 'aviation' },
        { text: 'ground', value: 'ground' },
        { text: 'helicopters', value: 'helicopters' }
      ],
      headers: []
    };
  },

  computed: {
    // Process headers for data table compatibility
    processedHeaders() {
      return this.headers.map(header => ({
        ...header,
        title: header.text,
        key: header.value,
        align: 'start',
        sortable: true
      }))
    }
  },

  watch: {
    // Watch for vehicle type changes
    selectedType: {
      immediate: true,
      handler() {
        this.updateHeaders();
        this.resetPagination();
        this.forceReload()
      }
    },
    // Watch for search term changes
    globalSearch(newVal, oldVal) {
      if (newVal !== oldVal) {
        this.$nextTick(() => {
          if (this.$refs.dataTable) {
            this.$refs.dataTable.updateOptions({ page: 1 });
          }
        });
      }
    }
  },

  methods: {
    // Update table headers based on selected vehicle type
    updateHeaders() {
      const commonHeaders = [
        { text: 'Name', value: 'name', width: 200, sortType: 'string' },
        { text: 'Nation', value: 'nation', width: 200 },
        { text: 'Rank', value: 'rank', width: 100, sortType: 'number' },
        { text: 'Price', value: 'purchase', width: 200, sortType: 'number' },
        { text: 'Research point', value: 'research', width: 200, sortType: 'number' },
        { text: 'AB', value: 'AB', width: 100, sortType: 'number' },
        { text: 'RB', value: 'RB', width: 100, sortType: 'number' },
        { text: 'SB', value: 'SB', width: 100, sortType: 'number' }
      ];

      const typeSpecificHeaders = {
        aviation: [
          { text: 'Crews', value: 'crew', width: 100, sortType: 'number' },
          { text: 'Max Speed(km/h)', value: 'max_speed', width: 100, sortType: 'number' },
          { text: 'Max speed at height(m)', value: 'at_height', width: 100, sortType: 'number' },
          { text: 'Flap Speed Limit ias(km/h)', value: 'flap_speed_limit_ias', width: 100, sortType: 'number' },
          { text: 'Gross Weight(t)', value: 'gross_weight', width: 100, sortType: 'number' },
          { text: 'Length(m)', value: 'length', width: 100, sortType: 'number' },
          { text: 'Mach Number Limit', value: 'mach_number_limit', width: 100, sortType: 'number' },
          { text: 'Max Altitude(m)', value: 'max_altitude', width: 100, sortType: 'number' },
          { text: 'Max Speed Limit ias(km/h)', value: 'max_speed_limit_ias', width: 100, sortType: 'number' },
          { text: 'Rate of Climb(m/s)', value: 'rate_of_climb', width: 100, sortType: 'number' },
          { text: 'Takeoff Run(m)', value: 'takeoff_run', width: 100, sortType: 'number' },
          { text: 'Turn time(秒)', value: 'turn_time', width: 100, sortType: 'number' },
          { text: 'Wingspan(m)', value: 'wingspan', width: 100, sortType: 'number' }
        ],
        ground: [
          { text: 'Crew', value: 'crew', width: 100, sortType: 'number' },
          { text: 'Engine Power(hp)', value: 'engine_power', width: 100, sortType: 'number' },
          { text: 'Max Speed Forward(km/h)', value: 'max_speed_forward', width: 100, sortType: 'number' },
          { text: 'Max Speed Backward(km/h)', value: 'max_speed_backward', width: 100, sortType: 'number' },
          { text: 'Weight(kg)', value: 'weight', width: 100, sortType: 'number' },
          { text: 'Power to weight ratio(hp/t)', value: 'power_to_weight_ratio', width: 100, sortType: 'number' },
          { text: 'Visibility(%)', value: 'visibility', width: 100, sortType: 'number' }
        ],
        helicopters: [
          { text: 'Max speed at height(m)', value: 'at_height', width: 100, sortType: 'number' },
          { text: 'Crew', value: 'crew', width: 100, sortType: 'number' },
          { text: 'Gross Weight(t)', value: 'gross_weight', width: 100, sortType: 'number' },
          { text: 'Main rotor diameter(m)', value: 'main_rotor_diameter', width: 100, sortType: 'number' },
          { text: 'Max altitude(m)', value: 'max_altitude', width: 100, sortType: 'number' },
          { text: 'Max speed(km/h)', value: 'max_speed', width: 100, sortType: 'number' },
          { text: 'Rate of climb(m/s)', value: 'rate_of_climb', width: 100, sortType: 'number' }
        ]
      };

      this.headers = [
        ...commonHeaders,
        ...(typeSpecificHeaders[this.selectedType] || [])
      ];
    },

    // Reset pagination data
    resetPagination() {
      this.serverItems = [];
      this.totalItems = 0;
    },

    // Force reload of table data
    forceReload() {
      
      if (this.$refs.dataTable && this.$refs.dataTable.updateOptions) {
        this.$refs.dataTable.updateOptions({
          page: 1,
          itemsPerPage: this.itemsPerPage,
          sortBy: [],
          sortDesc: []
        });
      } else {
        
        this.loadItems({
          page: 1,
          itemsPerPage: this.itemsPerPage,
          sortBy: []
        });
      }
    },

    mounted() {
      console.log('DataTable ref:', this.$refs.dataTable);
      console.log('UpdateOptions exists:', 
        this.$refs.dataTable?.updateOptions instanceof Function
      );
    },

    // Main data loading method
    async loadItems({ page, itemsPerPage, sortBy }) {
      this.isLoading = true;
      try {
        const validSort = this.validateSort(sortBy?.[0]);
        const params = {
          page: page || 1,
          limit: itemsPerPage || this.itemsPerPage,
          search: this.globalSearch?.trim() || '',
          sortBy: validSort?.key,
          sortOrder: validSort?.order || 'asc',
          type: this.selectedType
        };

        // Execute API request
        Object.keys(params).forEach(key => {
          if (params[key] === undefined || params[key] === null) delete params[key];
        });

        const response = await axios.get(`http://127.0.0.1:5000/${this.selectedType}`, { params });
        this.serverItems = response.data.items || [];
        this.totalItems = response.data.total || 0;

        // Validate received data structure
        if (this.serverItems.length > 0) {
          this.validateDataFields();
        }
      } catch (error) {
        this.handleLoadError(error);
      } finally {
        this.isLoading = false;
      }
    },

    validateSort(sort) {
      if (!sort) return null;
      const header = this.headers.find(h => h.value === sort.key);
      return header?.sortType ? {
        key: sort.key,
        order: sort.order || 'asc',
        type: header.sortType
      } : null;
    },

    validateDataFields() {
      const sampleItem = this.serverItems[0];
      if (!sampleItem) return;

      const missingFields = this.headers
        .filter(header => !(header.value in sampleItem))
        .map(header => header.value);

      if (missingFields.length > 0) {
        console.error('Missing fields:', missingFields);
        this.showErrorNotification('Data Mismatch', `Missing fields: ${missingFields.join(', ')}`);
      }
    },

    showErrorNotification(title, text) {
      console.error(title, text);
      
    },

    handleLoadError(error) {
      console.error('Loading failed:', error);
      this.showErrorNotification('Error', error.message || 'Failed to load data');
    },
    
    // Format cell values based on column type
    formatValue(item, key) {
      const value = item[key];
      if (value === null || value === undefined || value === '') return '--';

      switch(key) {
        case 'AB':
        case 'RB':
        case 'SB':
          return parseFloat(value).toFixed(1);
        
        case 'engine_power':
          return `${parseInt(value)} hp`;
        
        case 'weight':
          return `${parseFloat(value).toFixed(1)} t`;
        
        case 'armor_hull':
        case 'armor_turret':
          return value.replace(' mm', '') + ' mm';
        
        case 'power_to_weight_ratio':
          return `${parseFloat(value).toFixed(1)} hp/t`;
        
        case 'visibility':
          return `${parseInt(value)} %`;
        
        case 'optics_commander_zoom':
        case 'optics_driver_zoom':
        case 'optics_gunner_zoom':
          return value ? value.replace(/x/g, '×') : '--'; 
        
        case 'max_speed':
        case 'max_speed_forward':
        case 'max_speed_backward':
          return `${parseInt(value)} km/h`;
        
        case 'at_height':
        case 'max_altitude':
        case 'takeoff_run':
          return `${parseInt(value)} m`;
        
        case 'gross_weight':
          return `${parseFloat(value).toFixed(1)} t`; 
        
        case 'length':
        case 'wingspan':
        case 'main_rotor_diameter':
          return `${parseFloat(value).toFixed(1)} m`;
        
        case 'mach_number_limit':
          return `${parseFloat(value).toFixed(1)} Mach`;
        
        case 'rate_of_climb':
          return `${parseInt(value)} m/s`;
        
        case 'turn_time':
          return `${parseInt(value)} s`;
        
        case 'purchase':
          try {
            const numValue = parseFloat(String(value).replace(/,/g, ''));
            return isNaN(numValue) ? '--' : `${numValue.toLocaleString()} sl`;
          } catch {
            return '--';
          }
        
        default:
          return value?.toString() || '--';
      }
    }
  }
};
</script>

<style scoped>
.vehicle-list-container {
  background: #ffffff;
  border-radius: 8px;
  overflow: hidden;
}

.header-section {
  padding: 20px;
  background: #f8f9fa;
  border-bottom: 1px solid #dee2e6;
}

.filter-controls {
  display: grid;
  gap: 15px;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  margin-top: 20px;
}

.data-table {
  margin-top: 20px;
  border-radius: 6px;
  overflow: hidden;
}

:deep(.v-data-table-header) th {
  background-color: #f1f3f5 !important;
  font-weight: 600 !important;
  color: #2c3e50 !important;
  border-bottom: 2px solid #dee2e6 !important;
}

:deep(.v-data-table__tr) td {
  color: #495057 !important;
  border-bottom: 1px solid #e9ecef !important;
  transition: background-color 0.2s ease;
}

:deep(.v-data-table__tr:hover) td {
  background-color: #f8f9fa !important;
}

:deep(.v-text-field__details) {
  display: none;
}
</style>