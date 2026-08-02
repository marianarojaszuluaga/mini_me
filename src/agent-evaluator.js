/**
 * AGENT EVALUATOR - Independent Quality Assessment Layer
 *
 * Purpose: Evaluate quality of MAP agent outputs independently
 * Can be invoked directly via API with Anthropic token
 * Not dependent on the frontend application
 *
 * Usage:
 * ```
 * const evaluator = new AgentEvaluator(apiKey);
 * const result = await evaluator.evaluate(agentName, output, context);
 * ```
 */

const Anthropic = require("@anthropic-ai/sdk");

class AgentEvaluator {
  constructor(apiKey) {
    this.client = new Anthropic({ apiKey });
    // Scoring against a fixed, structured rubric is mechanical enough for
    // haiku — this can run on every single agent invocation, so it's the
    // highest-volume call in the system. Bump back to sonnet if scores start
    // looking unreliable in practice.
    this.model = "claude-3-5-haiku-20241022";

    this.evaluationCriteria = {
      gimena: {
        name: "Gimena - User Story Writer",
        dimensions: {
          format_compliance: {
            weight: 0.2,
            description: "HU format compliance (As/I want/For structure)"
          },
          completeness: {
            weight: 0.3,
            description: "Complete AC, error handling, visual references"
          },
          clarity: {
            weight: 0.2,
            description: "Language clarity, technical accuracy"
          },
          actionability: {
            weight: 0.2,
            description: "Clear next steps, no ambiguity"
          },
          alignment: {
            weight: 0.1,
            description: "Business & technical requirements met"
          }
        },
        targetScore: 90
      },

      gabi: {
        name: "Gabi - Work Planner",
        dimensions: {
          phase_completeness: {
            weight: 0.2,
            description: "All 5 phases detailed (DB→Backend→API→Frontend→Integration)"
          },
          tdd_strategy: {
            weight: 0.25,
            description: "Unit, Integration, API, E2E test strategies"
          },
          solid_application: {
            weight: 0.2,
            description: "All 5 SOLID principles documented"
          },
          estimations: {
            weight: 0.2,
            description: "Optimistic, Realistic, Pessimistic with confidence"
          },
          risk_management: {
            weight: 0.15,
            description: "Risk assessment with mitigation"
          }
        },
        targetScore: 85
      },

      gabriela: {
        name: "Gabriela - Project Brain",
        dimensions: {
          stakeholder_clarity: {
            weight: 0.2,
            description: "Complete stakeholder table with roles"
          },
          scope_definition: {
            weight: 0.25,
            description: "In/Out scope matrix clarity"
          },
          timeline_completeness: {
            weight: 0.15,
            description: "Start, end, milestones defined"
          },
          business_rules: {
            weight: 0.2,
            description: "Critical rules documented"
          },
          documentation_currency: {
            weight: 0.2,
            description: "Meeting log and change log up-to-date"
          }
        },
        targetScore: 90
      },

      santi: {
        name: "Santi - Meeting Minutes",
        dimensions: {
          format_compliance: {
            weight: 0.25,
            description: "H1/H2/H3 hierarchy correct (no H2 numbers)"
          },
          action_items: {
            weight: 0.25,
            description: "☐ symbol usage, owner, deadline"
          },
          language_precision: {
            weight: 0.2,
            description: "Direct language, no 'mentioned that' phrases"
          },
          risk_identification: {
            weight: 0.2,
            description: "Alerts and red flags clearly marked"
          },
          professional_tone: {
            weight: 0.1,
            description: "Executive, results-oriented tone"
          }
        },
        targetScore: 85
      },

      daniel: {
        name: "Daniel - Release Notes",
        dimensions: {
          technical_accuracy: {
            weight: 0.25,
            description: "Bitbucket version accuracy"
          },
          dual_version_coherence: {
            weight: 0.25,
            description: "Bitbucket ↔ Basecamp alignment"
          },
          audience_appropriateness: {
            weight: 0.2,
            description: "Technical vs client-friendly tone"
          },
          completeness: {
            weight: 0.2,
            description: "All commits, features, fixes included"
          },
          presentation: {
            weight: 0.1,
            description: "Professional, clear structure"
          }
        },
        targetScore: 90
      }
    };
  }

  /**
   * Main evaluation method
   */
  async evaluate(agentName, output, context = {}) {
    const criteria = this.evaluationCriteria[agentName] || this.genericCriteria(agentName);
    const prompt = this.buildEvaluationPrompt(agentName, criteria, output, context);

    try {
      const response = await this.client.messages.create({
        model: this.model,
        max_tokens: 2000,
        messages: [
          {
            role: "user",
            content: prompt
          }
        ]
      });

      const evaluationText = response.content[0].text;
      const scores = this.parseEvaluationResponse(evaluationText, criteria);

      return {
        agent: agentName,
        timestamp: new Date().toISOString(),
        scores: scores,
        targetScore: criteria.targetScore,
        status: this.getStatus(scores.overall, criteria.targetScore),
        feedback: evaluationText,
        dimensions: criteria.dimensions
      };
    } catch (error) {
      throw new Error(`Evaluation failed for ${agentName}: ${error.message}`);
    }
  }

  /**
   * Fallback criteria for agents without a bespoke rubric (e.g. the 14
   * spec-kit agents) so /evaluate never 400s on a known, invokable agent.
   */
  genericCriteria(agentName) {
    return {
      name: agentName,
      dimensions: {
        completeness: { weight: 0.3, description: "Output covers what was asked" },
        clarity: { weight: 0.25, description: "Clear, unambiguous" },
        adherence: { weight: 0.25, description: "Follows the agent's documented role/restrictions" },
        actionability: { weight: 0.2, description: "Next steps are clear" }
      },
      targetScore: 80
    };
  }

  /**
   * Batch evaluate multiple outputs
   */
  async evaluateBatch(evaluations) {
    const results = [];
    for (const item of evaluations) {
      const result = await this.evaluate(item.agent, item.output, item.context);
      results.push(result);
    }
    return results;
  }

  /**
   * Build evaluation prompt
   */
  buildEvaluationPrompt(agentName, criteria, output, context) {
    const dimensionsStr = Object.entries(criteria.dimensions)
      .map(
        ([key, value]) =>
          `- ${key.replace(/_/g, " ").toUpperCase()}: ${value.description} (Weight: ${value.weight * 100}%)`
      )
      .join("\n");

    return `You are a quality assurance specialist evaluating AI agent outputs for a project management system.

AGENT: ${criteria.name}
TARGET SCORE: ${criteria.targetScore}/100

EVALUATION DIMENSIONS:
${dimensionsStr}

CONTEXT:
${JSON.stringify(context, null, 2)}

OUTPUT TO EVALUATE:
${output}

EVALUATION TASK:
1. Score each dimension from 0-100 based on the criteria
2. Calculate weighted overall score
3. Identify red flags (critical issues)
4. Provide improvement recommendations
5. Determine if output meets quality standards

RESPONSE FORMAT (CRITICAL - MUST BE VALID JSON):
{
  "dimensions": {
    "dimension_name": {
      "score": <number 0-100>,
      "reasoning": "<explanation>"
    }
  },
  "overall": <weighted average>,
  "status": "<EXCELLENT|GOOD|WARNING|CRITICAL>",
  "redFlags": ["<flag1>", "<flag2>"],
  "recommendations": ["<rec1>", "<rec2>"],
  "summary": "<brief overall assessment>"
}`;
  }

  /**
   * Parse evaluation response
   */
  parseEvaluationResponse(text, criteria) {
    try {
      const jsonMatch = text.match(/\{[\s\S]*\}/);
      if (!jsonMatch) {
        throw new Error("No JSON found in response");
      }

      const evaluation = JSON.parse(jsonMatch[0]);

      let overall = evaluation.overall || 0;
      if (overall === 0) {
        let weightedScore = 0;
        let totalWeight = 0;

        for (const [dimension, weight] of Object.entries(criteria.dimensions)) {
          const score = evaluation.dimensions[dimension]?.score || 0;
          weightedScore += score * weight.weight;
          totalWeight += weight.weight;
        }

        overall = Math.round(weightedScore / totalWeight);
      }

      return {
        dimensions: evaluation.dimensions || {},
        overall: overall,
        status: evaluation.status || this.getStatus(overall, criteria.targetScore),
        redFlags: evaluation.redFlags || [],
        recommendations: evaluation.recommendations || [],
        summary: evaluation.summary || ""
      };
    } catch (error) {
      console.error("Parse error:", error);
      return {
        dimensions: {},
        overall: 0,
        status: "CRITICAL",
        redFlags: ["Evaluation parsing failed"],
        recommendations: ["Review agent output format"],
        summary: "Unable to parse evaluation"
      };
    }
  }

  /**
   * Determine status based on score
   */
  getStatus(score, targetScore) {
    if (score >= targetScore) return "EXCELLENT";
    if (score >= 75) return "GOOD";
    if (score >= 50) return "WARNING";
    return "CRITICAL";
  }

  /**
   * Generate report from multiple evaluations
   */
  generateReport(evaluations) {
    const report = {
      timestamp: new Date().toISOString(),
      totalEvaluations: evaluations.length,
      agents: {},
      overallMetrics: {
        averageScore: 0,
        excellentCount: 0,
        goodCount: 0,
        warningCount: 0,
        criticalCount: 0
      },
      trends: [],
      recommendations: []
    };

    let totalScore = 0;

    for (const item of evaluations) {
      totalScore += item.scores.overall;

      if (!report.agents[item.agent]) {
        report.agents[item.agent] = {
          latestScore: item.scores.overall,
          targetScore: item.targetScore,
          status: item.status,
          redFlags: item.scores.redFlags,
          recommendations: item.scores.recommendations
        };
      }

      if (item.status === "EXCELLENT") report.overallMetrics.excellentCount++;
      if (item.status === "GOOD") report.overallMetrics.goodCount++;
      if (item.status === "WARNING") report.overallMetrics.warningCount++;
      if (item.status === "CRITICAL") report.overallMetrics.criticalCount++;
    }

    report.overallMetrics.averageScore = evaluations.length
      ? Math.round(totalScore / evaluations.length)
      : 0;

    return report;
  }
}

module.exports = AgentEvaluator;
