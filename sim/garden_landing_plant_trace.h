/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_LANDING_PLANT_TRACE_H_
#define TOY_FACTORY_GARDEN_LANDING_PLANT_TRACE_H_

#include "garden_landing_growth.h"
#include "garden_seedling_reserve.h"
#include <stdio.h>

enum toy_factory_garden_plant_trace_scope {
	TOY_FACTORY_GARDEN_TRACE_FOUNDERS,
	TOY_FACTORY_GARDEN_TRACE_ALL,
	TOY_FACTORY_GARDEN_TRACE_ORDERED,
	TOY_FACTORY_GARDEN_TRACE_CHOICE,
	TOY_FACTORY_GARDEN_TRACE_ENERGY,
	TOY_FACTORY_GARDEN_TRACE_AFTERNOON,
	TOY_FACTORY_GARDEN_TRACE_DAYLIGHT,
	TOY_FACTORY_GARDEN_TRACE_DAWN,
	TOY_FACTORY_GARDEN_TRACE_SCOPES,
};

struct toy_factory_garden_plant_bid {
	uint32_t lineage;
	struct picosystem_garden_agent_observation observation;
	uint8_t raw_action;
	uint8_t action;
	int16_t priority;
	int16_t raw_priority;
	struct toy_factory_garden_budget_receipt budget;
	struct toy_factory_garden_seedling_reserve_forecast water;
	bool water_active;
	bool energy_active;
	bool afternoon_active;
	struct toy_factory_garden_afternoon_forecast afternoon;
	bool daylight_active;
	struct toy_factory_garden_daylight_forecast daylight;
	bool dawn_active;
	struct toy_factory_garden_root_allocation_receipt allocation;
	struct toy_factory_garden_dawn_forecast dawn;
	struct picosystem_garden_agent_proposal direction;
	struct picosystem_garden_agent_proposal raw_direction;
	uint8_t root_cells[(PICOSYSTEM_GARDEN_SOIL_CELL_COUNT + 7U) / 8U];
};

/* One host owner; borrowed stream outlives the collector. At most one query per
 * active tip per ecology step. Publish only after success; incomplete files are
 * invalid, and errors do not roll back the external collector or stream.
 */
struct toy_factory_garden_plant_trace {
	FILE *stream;
	enum toy_factory_garden_plant_trace_scope scope;
	uint32_t founders[PICOSYSTEM_GARDEN_MAX_PLANTS];
	uint8_t founder_count;
	uint8_t budget_mode;
	uint16_t count;
	bool directions_enabled;
	struct toy_factory_garden_root_choice root_choice;
	struct toy_factory_garden_root_allocation root_allocation;
	struct toy_factory_garden_plant_bid bids[PICOSYSTEM_GARDEN_MAX_NODES];
	struct picosystem_garden_reproduction_audit reproduction;
};

int toy_factory_garden_plant_trace_init(struct toy_factory_garden_plant_trace *trace, FILE *stream,
					const struct picosystem_garden_world *initial,
					uint8_t limit, uint8_t budget_mode, uint32_t start,
					uint32_t stop,
					enum toy_factory_garden_plant_trace_scope scope);
int toy_factory_garden_plant_trace_observe(
	const struct picosystem_garden_world *world,
	const struct picosystem_garden_agent_observation *observation,
	const struct picosystem_garden_agent_decision *raw,
	const struct picosystem_garden_agent_decision *applied, void *context);
int toy_factory_garden_plant_trace_publish(struct toy_factory_garden_plant_trace *trace,
					   const struct picosystem_garden_world *world);
int toy_factory_garden_plant_directions_publish(const struct toy_factory_garden_plant_trace *trace,
						const struct picosystem_garden_world *world,
						FILE *stream);

#endif
