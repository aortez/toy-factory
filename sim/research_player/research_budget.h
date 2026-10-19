/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_RESEARCH_BUDGET_H_
#define TOY_FACTORY_RESEARCH_BUDGET_H_

#include "garden_maintenance_step.h"
#include "garden_reproduction_audit.h"
#include <stdio.h>

#define RESEARCH_BUDGET_LINEAGE 17U
#define RESEARCH_BUDGET_LIMIT   2560U
#define RESEARCH_BUDGET_FIRST   583215U
#define RESEARCH_BUDGET_END     868380U

/* Fixed observation windows, not policy inputs. Exclusive session owner,
 * one bounded allocation, no step allocation or retained borrowed pointers.
 * Discard the collector after any record error; the session latches failures.
 */
struct research_budget;
bool research_budget_active(uint32_t tick);
int research_budget_open(struct research_budget **out);
void research_budget_close(struct research_budget *trace);
int research_budget_record(struct research_budget *trace,
			   const struct toy_factory_maintenance_step *step,
			   const struct picosystem_garden_reproduction_audit *audit);
int research_budget_write(const struct research_budget *trace, FILE *stream);

#endif
